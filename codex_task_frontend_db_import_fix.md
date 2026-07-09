# Codex 任务简报：禁止 FrontendExpert 写 try/except 兜底导入 db 模块

> 按 CLAUDE.md「委派 Codex 处理代码修改的规范」五项要求撰写。这是本任务唯一一次
> 派发简报——不会有后续"补充版"或"完整版"，Codex 应该按这一份完整执行。

## 1. 修改范围

**只改一个文件、一处字符串常量**：
[backend/agents/experts/frontend_expert.py](backend/agents/experts/frontend_expert.py)
里的 `FRONTEND_SYSTEM_PROMPT` 字符串常量（当前第 20-29 行）。

**明确不许碰的文件/代码**（越界了就是这次任务失败，不是"顺手改进"）：
- 同一个文件里的 `_extract_code()`、`_assert_tkinter_app()`、`_build_retry_feedback()`、
  `frontend_expert_node()` 等其他函数**一个字都不许改**，只改
  `FRONTEND_SYSTEM_PROMPT` 这一个字符串常量
- `backend/agents/experts/backend_expert.py`、`test_expert.py`——这次只约束
  FrontendExpert 一个人的行为
- `backend/skills/build/SKILL.md`、`backend/skills/frontend-ui/SKILL.md`——
  这次要加的规则直接写进 `FRONTEND_SYSTEM_PROMPT` 这个专属字符串里，不动共用
  或专属的技能文件
- `backend/graph/workflow.py`、任何 `backend/agents/validator/**`、`output/`
  目录下任何文件、任何其他 `SKILL.md`

## 2. 修改目标

**具体问题（真实复现，不是假设）**：真实启动了一次"个人记账应用"生成结果，
用 pywinauto 脚本模拟真实用户操作——真实填表单、真实点击"添加"按钮，弹出
错误对话框：`数据库错误 - 添加失败：name 'db' is not defined`，100% 复现。

根因是生成的 `app.py` 开头写了这样的代码：

```python
try:
    import db as _db
except ImportError:
    # 内存数据库，模拟 db 模块（方便在没有真实数据库时运行）
    ...FakeDB 兜底...
```

模块被起了别名 `_db`，但业务逻辑代码（`add_transaction()` 方法）实际调用的是
`db.create_transaction(...)`——裸名字 `db` 在这份文件里从未被绑定过，一调用
就是 `NameError`。用户反馈这个报错在实际使用中经常出现，不是这次生成的偶然
个例，是可复现的模式。

**为什么会写出这种代码**：`db.py` 和 `app.py` 由同一条流水线在同一个输出
目录里生成，两个文件必然同时存在，不可能出现"导入 db 失败"这种场景。但
`FRONTEND_SYSTEM_PROMPT` 当前只写了"从 db 模块 import 函数（按接口规范的
函数名）"，没有明确禁止"给这个必然存在的模块写防御性 try/except 兜底导入"
这类没必要的写法——这类"优雅降级"式防御代码在通用 Python 训练语料里很常见，
AI 会在没被要求的情况下主动写，而这个结构（导入时起别名、业务逻辑用原名）
天然容易在两处之间前后不一致。

**目标**：直接在 `FRONTEND_SYSTEM_PROMPT` 里加一条硬性规则，禁止这类
try/except 兜底导入，要求直接用 `from db import 具体函数名` 导入，从源头上
消除"起别名的导入语句"和"业务逻辑调用"之间可能对不上的风险。

## 3. 具体修改措施

把 `frontend_expert.py` 里 `FRONTEND_SYSTEM_PROMPT` 当前的完整原文
（第 20-29 行）：

```python
FRONTEND_SYSTEM_PROMPT = """你是一位专业的 Python 桌面 UI 工程师。
你的任务是根据接口规范，用 Python + Tkinter 实现桌面应用界面。

要求：
- 只用标准库 tkinter，不引入额外依赖
- 从 db 模块 import 函数（按接口规范的函数名）
- 界面要有：输入框、添加按钮、任务列表、删除按钮
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 代码要能直接运行，if __name__ == '__main__': 启动主循环
""" + "\n\n" + load_skill_prompt("build") + "\n\n" + load_skill_prompt("frontend-ui")
```

替换成（只在"要求"列表里插入一条新规则，其余逐字不变）：

```python
FRONTEND_SYSTEM_PROMPT = """你是一位专业的 Python 桌面 UI 工程师。
你的任务是根据接口规范，用 Python + Tkinter 实现桌面应用界面。

要求：
- 只用标准库 tkinter，不引入额外依赖
- 从 db 模块 import 函数（按接口规范的函数名）：直接写
  `from db import 函数名1, 函数名2, ...`，不要写 try/except ImportError
  这类防御性兜底导入（比如"导入失败就用内存字典/类模拟一个假的 db 模块"）。
  db.py 和 app.py 由同一条流水线写进同一个输出目录，必然同时存在，不会出现
  导入失败的场景，这类兜底代码没有意义，反而容易在"给模块起别名"和"后续
  代码实际用哪个名字调用"之间写岔（例如写了 `import db as _db`，业务逻辑
  却调用 `db.xxx()`，`db` 这个名字根本没被定义过，一调用就 NameError 崩溃）
- 界面要有：输入框、添加按钮、任务列表、删除按钮
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 代码要能直接运行，if __name__ == '__main__': 启动主循环
""" + "\n\n" + load_skill_prompt("build") + "\n\n" + load_skill_prompt("frontend-ui")
```

除了这一条新增规则，`FRONTEND_SYSTEM_PROMPT` 其余文字、文件里的其他函数
都不许动。

## 4. Codex 自验证方法（改完必须自己做，不做不算交付）

1. 改完后重新读一遍 `frontend_expert.py` 完整文件，确认只有
   `FRONTEND_SYSTEM_PROMPT` 这个字符串常量发生变化，文件里其他函数
   （`_extract_code`、`_assert_tkinter_app`、`_build_retry_feedback`、
   `frontend_expert_node` 等）逐字未动。
2. 在项目根目录用 `.venv\Scripts\python.exe` 实际执行：
   ```
   python -c "from backend.agents.experts.frontend_expert import FRONTEND_SYSTEM_PROMPT; print(FRONTEND_SYSTEM_PROMPT)"
   ```
   确认能正常导入、没有语法错误或异常，且打印出的内容里包含新增的这条禁止
   兜底导入的规则，把真实终端输出贴出来。
3. 跑 `git diff --stat` 确认改动范围只有
   `backend/agents/experts/frontend_expert.py` 这一个文件，贴出真实输出。
4. **不需要**（也不应该）重新触发一次完整的 DeepSeek 生成 + Validator 全链路
   跑一遍——那需要真实 API Key、跑 5-10 分钟、消耗真实 token 额度，这个决定
   应该留给人类。Codex 只需要验证"文件改对了、能被正常导入、没有越界改动
   其它文件"。

## 5. 验收标准（人类复核时要确认这些）

用 `Read` 工具直接读取 `backend/agents/experts/frontend_expert.py` 改动后的
**当前**完整内容（不要只看 diff），确认：

- [ ] `FRONTEND_SYSTEM_PROMPT` 里新增了一条明确禁止 try/except ImportError
      防御性兜底导入 db 模块的规则，并且写清楚了原因（db.py/app.py 必然同时
      存在、兜底代码容易在别名和实际调用名字之间写岔导致 NameError）
- [ ] `FRONTEND_SYSTEM_PROMPT` 里原有的其余规则（只用标准库、从 db 模块
      import 函数、界面组成、代码块格式、`if __name__ == '__main__'`）逐字
      未变
- [ ] 文件里其他函数（`_extract_code`、`_assert_tkinter_app`、
      `_build_retry_feedback`、`frontend_expert_node` 等）逐字未变
- [ ] Codex 贴出的
      `python -c "from ... import FRONTEND_SYSTEM_PROMPT; print(...)"`
      真实调用结果里，能看到新规则的完整文字（不是异常堆栈）
- [ ] `git diff --stat` 显示改动只涉及
      `backend/agents/experts/frontend_expert.py` 这一个文件，没有出现
      `backend_expert.py`、`test_expert.py`、
      `backend/skills/build/SKILL.md`、`backend/skills/frontend-ui/SKILL.md`、
      `workflow.py`、`backend/agents/validator/**`、`output/` 目录下任何
      文件的改动

验收通过后，下一步（人类决定是否要做，不属于本次 Codex 任务）：backend 进程
需要重启才能加载这个新 Prompt（当前没有 `--reload`），下次重新跑生成时观察
FrontendExpert 是否还会写这类防御性兜底导入代码。
