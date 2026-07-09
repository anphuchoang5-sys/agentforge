# Codex 任务简报：修复 Validator 启动生成应用时未隔离工作目录的 bug

> 按 CLAUDE.md「委派 Codex 处理代码修改的规范」五项要求撰写。这是本任务唯一一次
> 派发简报——不会有后续"补充版"或"完整版"，Codex 应该按这一份完整执行。

## 1. 修改范围

**只改一个文件、一处调用**：[backend/agents/validator/run.py](backend/agents/validator/run.py)
的 `_launch_app()` 函数（当前第 139-205 行）里第 164 行的 `_sp.Popen(...)` 调用。

**明确不许碰的文件/代码**（越界了就是这次任务失败，不是"顺手改进"）：
- `_launch_app()` 函数内其余逻辑（窗口轮询、`Application.connect`、错误处理）
  **一个字都不许改**，只加一个 `cwd` 参数
- `_cleanup_app()`、`_launch_and_screenshot()`、`_execute_interaction_plan()`、
  `_ui_interaction_check()`——这几个函数调用 `_launch_app()`，但函数体本身跟这次
  改动无关，不要动
- `backend/mcp_tools/desktop_control.py`、`backend/agents/validator/checkers.py`——
  不在本次范围内
- `backend/agents/experts/backend_expert.py`、`frontend_expert.py`、
  `test_expert.py`——生成代码的专家 Agent 本身没有问题，不要动
- `backend/graph/workflow.py`——编排逻辑，跟这次问题无关
- **不要删除或修改根目录的 `app.db` 文件**——那是历史遗留的脏数据，清理是否需要
  由人类决定，不属于这次"修 bug"的任务范围
- `output/` 目录下任何文件

## 2. 修改目标

**具体问题**：`_launch_app()` 第 164 行

```python
proc = _sp.Popen([launcher, app_path], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
```

启动生成的桌面应用子进程时**没有传 `cwd` 参数**。Python 的 `subprocess.Popen`
在不传 `cwd` 时，子进程会原样继承父进程（也就是运行 Validator 服务本身的进程）
的当前工作目录。`.claude/launch.json` 里 `validator` 这个启动配置没有指定
`cwd`，默认就是仓库根目录 `E:\6.29agent`。

而这个项目里所有生成的应用（`BackendExpert` 生成的 `db.py`）都按照
"生成文件名通用化"的约定统一写死相对路径 `sqlite3.connect("app.db")`——这个
相对路径不是相对于应用自己的输出目录（如 `output/account_book/`），而是相对于
**当前进程的工作目录**。既然 `_launch_app()` 启动子进程时没有指定 `cwd`，子
进程的工作目录就是继承来的仓库根目录，`sqlite3.connect("app.db")` 因此会解析
成 `E:\6.29agent\app.db`，不是 `output/account_book/app.db`。

**实测证据**（真实发现，不是推测）：仓库根目录当前的 `app.db` 里存在
10 张来自完全不同应用的表——`books`、`notes`、`dice_history`、`counter`、
`memos`、`todos`、`reminders`、`calculator_state`，以及两个不同版本的记账
应用表 `transactions`（列：`id/amount/category/type/date/note`）和
`records`（列：`id/type/amount/category/date/description`）。这证明只要
Validator 启动过某个生成的应用一次，这个应用的数据库读写就会落到仓库根目录，
跟其他历史生成的应用共享同一个文件，且列结构可能互相冲突——如果新生成的应用
表名恰好和某个历史应用重名但结构不同，`CREATE TABLE IF NOT EXISTS` 会直接
复用旧表结构，实际写入时会因为列名不匹配而报 `sqlite3.Error`，然后被
`create_transaction()` 这类函数的 `except sqlite3.Error` 吞掉、返回 `-1`——
界面上会显示"添加成功，ID: -1"，看起来像成功了，实际数据没有正确写入。

**对比证明这是可修的、局部的问题，不是设计缺陷**：同一个代码库里
[backend/agents/experts/test_expert.py:143](backend/agents/experts/test_expert.py#L143)
和第 183 行运行 pytest 子进程时，正确传了 `cwd=state["app_output_dir"]`，
所以 TestExpert 那条链路完全没有这个问题，pytest 每次都在正确的应用目录下
运行、数据库隔离良好。`_launch_app()` 只是漏掉了同样的处理，照着这个已有的
正确写法改就行。

**目标**：让 `_launch_app()` 启动的子进程工作目录设为生成应用所在的目录（也就是
`app_path` 的父目录），跟 `test_expert.py` 已经验证过的做法保持一致，使每个
生成应用的数据库真正隔离在自己的输出目录里，不再跟其他应用共享/冲突。

## 3. 具体修改措施

`_launch_app()` 函数开头已经有（第 146 行）：

```python
app_path_obj = Path(app_path)
if not app_path_obj.exists():
    raise FileNotFoundError(f"应用文件不存在: {app_path}")
```

`app_path_obj` 这个变量在整个函数作用域内都可用，第 164 行改的时候直接复用它，
不需要新建变量、不需要新增 import（`Path` 已经在文件顶部导入）。

把第 164 行原文：

```python
        proc = _sp.Popen([launcher, app_path], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
```

改成：

```python
        proc = _sp.Popen(
            [launcher, app_path],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            cwd=str(app_path_obj.parent),
        )
```

除了这一处，函数其余部分（第 139-163 行、166-205 行）逐字不变。

## 4. Codex 自验证方法（改完必须自己做，不做不算交付）

1. 改完后重新读一遍 `_launch_app()` 完整函数体，确认只有第 164 行附近的
   `Popen` 调用发生变化，其余逻辑逐字未动。
2. **写一个真实可执行的探针脚本，实际验证 cwd 隔离生效**，不要只做静态检查：
   - 在一个独立的临时目录（例如
     `C:\Windows\Temp\claude_codex_cwd_probe\probe_app.py`，跟仓库根目录不同）
     写一个最小 Tkinter 应用：
     ```python
     import os
     import tkinter as tk

     with open("cwd_marker.txt", "w", encoding="utf-8") as f:
         f.write(os.getcwd())

     root = tk.Tk()
     root.title("CWD Probe")
     root.geometry("200x100")
     root.after(4000, root.destroy)  # 4 秒后自动关闭，避免测试挂起
     root.mainloop()
     ```
   - 在项目根目录用 `.venv\Scripts\python.exe` 执行一段脚本，直接调用修改后的
     `backend.agents.validator.run._launch_app(探针脚本的绝对路径, [])`（内部
     函数，直接 import 调用即可，不需要经过完整的 validate() 流程），等它返回
     或探针窗口自动关闭后：
     - 检查 `cwd_marker.txt` 是否出现在探针脚本**自己所在的临时目录**里
       （而不是仓库根目录 `E:\6.29agent`）
     - 读取 `cwd_marker.txt` 的内容，确认等于探针脚本所在的临时目录路径
   - 把真实终端输出（包括 `_launch_app` 的返回值/日志、`cwd_marker.txt` 的
     真实内容）贴出来，不要用"应该会正常工作"这类话代替真实验证结果
   - 测试完成后清理这个临时探针目录，不要留在系统里
3. 跑 `git diff --stat` 确认改动范围只有 `backend/agents/validator/run.py`
   一个文件，贴出真实输出。

## 5. 验收标准（人类复核时要确认这些）

用 `Read` 工具直接读取 `backend/agents/validator/run.py` 改动后 `_launch_app()`
函数的**当前**完整内容（不要只看 diff），确认：

- [ ] 第 164 行附近的 `Popen(...)` 调用新增了 `cwd=str(app_path_obj.parent)`
      参数，且复用的是函数开头已有的 `app_path_obj` 变量，没有新增无关变量或
      import
- [ ] 函数其余部分（窗口轮询循环、`Application.connect`、异常处理、
      `_cleanup_app` 调用）逐字未变
- [ ] Codex 贴出的探针脚本真实运行结果显示：`cwd_marker.txt` 出现在探针脚本
      自己的临时目录里，内容也确实是那个临时目录路径，而不是仓库根目录——
      这是证明 cwd 隔离真的生效的关键证据，不能跳过
- [ ] `git diff --stat` 显示改动只涉及 `backend/agents/validator/run.py`
      这一个文件，没有出现 `checkers.py`、`desktop_control.py`、任何专家
      Agent 文件、`workflow.py`、根目录 `app.db`、`output/` 目录下任何文件
      的改动

验收通过后，下一步（人类决定是否要做，不属于本次 Codex 任务）：考虑是否要清理
根目录那个被污染的历史 `app.db`——里面混着 10 个不同历史生成应用的表，现在这个
cwd 修复只保证"以后"的生成应用不会再往这个文件里写，不会自动清理已经存在的
脏数据。
