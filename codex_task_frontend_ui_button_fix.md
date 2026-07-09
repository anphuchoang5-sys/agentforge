# Codex 任务简报：修复 frontend-ui 技能里的 ttk 按钮/Label 规则

> 按 CLAUDE.md「委派 Codex 处理代码修改的规范」五项要求撰写。这是本任务唯一一次
> 派发简报——不会有后续"补充版"或"完整版"，Codex 应该按这一份完整执行。

## 1. 修改范围

**只改一个文件**：[backend/skills/frontend-ui/SKILL.md](backend/skills/frontend-ui/SKILL.md)

- 具体位置：规则 1（当前第 21-24 行"一律用 ttk，不用裸 tk 控件"）+ 质量检查点
  第一条（当前第 54 行"全程没有出现裸 tk.Button/tk.Entry/tk.Listbox"）
- frontmatter（`name`/`description`/`level`/`agents`，第 1-6 行）**一个字都不许改**
- 规则 2-6（主题设置、间距节奏、配色、字号层次、Treeview 用法）**不许改**，跟这次
  问题无关

**明确不许碰的文件/目录**（越界了就是这次任务失败，不是"顺手改进"）：
- `backend/agents/experts/frontend_expert.py`、`backend_expert.py` 等任何专家
  Agent 代码——这次只改 prompt 依据的技能文档，不改调用逻辑
- `backend/mcp_tools/desktop_control.py`——这是 C 负责的 UI 自动化验证器代码，
  不在本次任务范围内，哪怕你认为"顺便也能改验证器让它认识 ttk 按钮"也不要动
- `backend/graph/workflow.py`——编排逻辑，跟这次问题无关
- `output/` 目录下任何文件（包括 `output/account_book/*`）——那是某一次运行生成
  的产物，不是项目代码，不需要也不应该手工修复
- 除 `frontend-ui` 以外的任何 `backend/skills/**/SKILL.md`

## 2. 修改目标

**具体问题**：刚跑通的一次真实需求（"个人记账应用"）里，UI 交互验证
（`ui_interact`）连续 5 轮全部在同一步失败："button_order_hint=1 超出按钮数量(0)"。
根因已经用真实日志 + 读代码确认，不是猜测：

- Validator 的 [backend/mcp_tools/desktop_control.py:146](backend/mcp_tools/desktop_control.py#L146)
  `list_buttons()` 实现是 `window.descendants(class_name="Button")`——按 **Windows
  原生控件类名**扫描。经典 `tk.Button` 在 Windows 上会生成对应的原生 `Button` 类型
  子窗口，能被扫到；`ttk.Button` 是主题绘制控件，不会生成这个类名，对这个扫描
  **完全不可见**。
- 但 `frontend-ui/SKILL.md` 当前规则 1 要求 FrontendExpert "一律用 ttk"，导致这次
  生成的 [output/account_book/app.py](output/account_book/app.py) 里"添加"
  （第172行）、"删除"（第206行）、"查询"（第223行）三个主按钮全部是
  `ttk.Button`——`list_buttons()` 永远扫到 0 个按钮，任何点击计划必然失败。
- 同样的问题理论上也影响结果类 Label（`list_labels()` 按 `class_name="Static"`
  扫描，`ttk.Label` 同样不会生成这个类名）。这次生成的 app.py 里，月度统计的三个
  结果 Label（第229-242行）已经是 `tk.Label` 并注释"以确保 UI 交互测试能够识别到
  Label 控件"——但这只是模型某一轮重试中自己摸索出的局部补丁，技能文件里从未
  写过这条规则，不稳定，下次生成不一定还会这样写。

**目标**：把这个"按钮/结果 Label 必须用经典 tk 控件"的规则写进
`frontend-ui/SKILL.md`，让 FrontendExpert 每次生成都直接遵守，而不是靠重试轮次
里偶然踩对。这个改动预期能让 UI 交互验证从"每次必然失败"变成"能真正测出实际
交互效果"，减少大量无效重试轮次和 token 消耗。

**范围要收紧，不要过度修改**：`ttk.Entry`/`ttk.Combobox`/`ttk.Spinbox`/
`ttk.Frame`/`ttk.Treeview` 这几类控件在这次日志的全部 5 轮里从未出现"输入框数量
不足"之类的检测失败，说明它们能被 `list_inputs()`（`class_name="TkChild"`）正常
识别，**不需要改，也不能顺手一起改成裸 tk**——只有"按钮"和"会被验证读取数值
变化的结果 Label"这两类需要例外。

## 3. 具体修改措施

把 `backend/skills/frontend-ui/SKILL.md` 当前的规则 1（原文如下）：

```markdown
1. **一律用 `ttk`，不用裸 `tk` 控件**：`ttk.Button`/`ttk.Entry`/`ttk.Frame`/
   `ttk.Label` 代替 `tk.Button`/`tk.Entry`/`tk.Frame`/`tk.Label`。列表类数据
   （有多个字段要并排显示，比如"标题+状态+日期"）用 `ttk.Treeview` 而不是
   `tk.Listbox`——`Listbox` 只能塞纯文本，多字段拼一行会显得很挤很业余。
```

替换成：

```markdown
1. **默认用 `ttk`，但两类控件必须用经典 `tk`，不能用 `ttk`**：

   - **默认（大多数场景）**：`ttk.Entry`/`ttk.Frame`/`ttk.Combobox`/
     `ttk.Spinbox`/`ttk.Treeview` 代替对应的裸 `tk` 控件——这些控件已验证过
     可以被 UI 自动化测试正常识别，维持 ttk 的现代观感。列表类数据（有多个
     字段要并排显示，比如"标题+状态+日期"）用 `ttk.Treeview` 而不是
     `tk.Listbox`——`Listbox` 只能塞纯文本，多字段拼一行会显得很挤很业余。

   - **例外 1：会触发状态变化的主操作按钮，必须用 `tk.Button`，不能用
     `ttk.Button`**——包括但不限于"添加/提交"、"删除"、"查询/统计"，以及
     弹窗里的"确定/是/否"这类按钮。原因：UI 自动化验证工具通过 Windows
     原生控件类名扫描按钮（`class_name="Button"`），`tk.Button` 在 Windows
     上会生成对应的原生 Button 类型窗口，`ttk.Button` 是主题绘制控件，不会
     生成这个类名，对自动化扫描完全不可见——用 `ttk.Button` 会导致验证阶段
     永远扫描到 0 个按钮，所有点击测试必然失败。用 `tk.Button` 手动设置样式
     模拟 ttk 的观感（例如 `bg="#4A90D9", fg="white",
     font=("Segoe UI", 10), relief="flat", bd=0, padx=8, pady=4,
     activebackground="#357ABD", cursor="hand2"`），不要用默认的
     Windows 95 灰色按钮外观。

   - **例外 2：会被验证读取数值变化的结果类 Label（如统计/汇总数值），必须用
     `tk.Label`，不能用 `ttk.Label`**——原因与按钮相同：验证工具按原生控件
     类名 `class_name="Static"` 扫描 Label，`ttk.Label` 同样不会生成这个
     类名。纯装饰性、不会被验证读取内容变化的标题/说明文字 Label 仍然可以用
     `ttk.Label`。
```

同时把质量检查点（当前第 53-58 行）里跟旧规则矛盾的第一条：

```markdown
- [ ] 全程没有出现裸 `tk.Button`/`tk.Entry`/`tk.Listbox`（多字段列表场景下）
```

替换成三条（跟新规则对应）：

```markdown
- [ ] 会触发状态变化的主操作按钮（添加/删除/查询/确认等）用的是 `tk.Button`，
      不是 `ttk.Button`
- [ ] 会被验证读取数值变化的结果类 Label 用的是 `tk.Label`，不是 `ttk.Label`
- [ ] 除上述两类例外，其余控件（Entry/Frame/Combobox/Spinbox/Treeview）保持
      `ttk`，没有被顺手改成裸 `tk`
```

其余质量检查点（主题、padx/pady、强调色、字号层次）保持不变。

## 4. Codex 自验证方法（改完必须自己做，不做不算交付）

1. 改完后完整重新读一遍 `backend/skills/frontend-ui/SKILL.md`，确认：
   - Markdown 格式没坏（标题层级、列表缩进、代码块围栏都正确闭合）
   - frontmatter（第 1-6 行）与改动前逐字一致
   - 规则 2-6 与改动前逐字一致
2. 实际调用一次 `backend/skills/loader.py::load_skill_prompt("frontend-ui")`
   （比如 `python -c "from backend.skills.loader import load_skill_prompt;
   print(load_skill_prompt('frontend-ui'))"`，在项目根目录、用
   `.venv\Scripts\python.exe` 执行），确认能正常加载出新内容、没有异常，把
   真实终端输出贴出来。
3. 跑 `git diff --stat` 确认改动范围**只有** `backend/skills/frontend-ui/SKILL.md`
   这一个文件，贴出真实输出。
4. **不需要**（也不应该）重新触发一次完整的 DeepSeek 生成 + Validator 全链路
   跑一遍——那需要真实 API Key、跑 5-10 分钟、消耗真实 token 额度，这个决定
   应该留给人类，不是 Codex 自己决定要不要跑。Codex 只需要验证"文件改对了、
   能被正常加载、没有越界改动其它文件"。

## 5. 验收标准（人类复核时要确认这些）

用 `Read` 工具直接读取 `backend/skills/frontend-ui/SKILL.md` 改动后的**当前**
完整内容（不要只看 diff，要看完整文件），确认：

- [ ] 规则 1 已经变成"默认 ttk + 两个例外"的结构，例外 1 明确点名"添加/删除/
      查询/确认"这类主操作按钮要用 `tk.Button`，并且写清楚了原因（win32
      `class_name="Button"` 扫描机制）
- [ ] 例外 2 同样覆盖"会被验证读取数值变化的结果类 Label"要用 `tk.Label`，
      原因写清楚了（`class_name="Static"` 扫描机制）
- [ ] 质量检查点第一条已经替换成新的三条，不再是跟新规则矛盾的旧表述
- [ ] frontmatter 和规则 2-6 逐字未变
- [ ] `git diff --stat` 显示改动只涉及这一个文件，没有出现
      `frontend_expert.py`、`desktop_control.py`、`workflow.py`、
      `output/` 目录下任何文件的改动
- [ ] Codex 贴出的 `load_skill_prompt("frontend-ui")` 真实调用结果里，能看到
      新规则的文字内容（不是异常堆栈）

验收通过后，下一步（人类决定是否要做，不属于本次 Codex 任务）：用同一个
"个人记账应用"需求重新跑一次全流程，对比这次改动前后 `ui_interact` 是否还会
卡在"按钮数量(0)"这一步。
