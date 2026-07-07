---
name: frontend-ui
description: 桌面界面视觉规范 — 只给 FrontendExpert 用，不影响 BackendExpert 的 prompt
level: L2
agents: [FrontendExpert]
---

# /frontend-ui 技能

技术栈只有 Tkinter 标准库，没有第三方主题库（不能用 customtkinter/sv-ttk 这类
需要 pip install 的东西），审美目标不是花哨，是"干净、克制、不像 2005 年的
Motif 默认灰"——参考 Claude 系列产品的界面气质：极简、留白够、层次靠字号和
间距区分，不是靠边框和颜色堆出来的。

## 激活时机
`FrontendExpert` 生成/重新生成界面代码时，跟 `/build` 技能一起生效（`/build`
管功能正确性，这份管视觉呈现，两者不冲突）。

## 执行规则

1. **一律用 `ttk`，不用裸 `tk` 控件**：`ttk.Button`/`ttk.Entry`/`ttk.Frame`/
   `ttk.Label` 代替 `tk.Button`/`tk.Entry`/`tk.Frame`/`tk.Label`。列表类数据
   （有多个字段要并排显示，比如"标题+状态+日期"）用 `ttk.Treeview` 而不是
   `tk.Listbox`——`Listbox` 只能塞纯文本，多字段拼一行会显得很挤很业余。

2. **开局先设主题**：窗口创建后立刻执行
   ```python
   style = ttk.Style()
   style.theme_use("clam")
   ```
   `clam` 主题比系统默认主题更扁平、更可控，不用 `default`/`classic`。

3. **8px 间距节奏**：所有 `padx`/`pady` 只从 `8`/`16`/`24` 里选，不要随手写
   `5`/`3`/`10` 这种没有规律的数字。外层容器（窗口根 Frame）至少留
   `padx=16, pady=16`，不要让控件贴着窗口边缘。

4. **一个主色 + 中性色，不要彩虹按钮**：整个界面选一个强调色（比如一个蓝色
   或绿色）用在"主要操作"按钮上（添加/提交这类），其余按钮和背景保持中性
   （白/浅灰）。不要每个按钮配一个不同颜色。

5. **层次靠字号和字重，不靠加框**：标题类文字用大字号+加粗
   （如 `font=("Segoe UI", 16, "bold")`），正文用常规字号
   （如 `font=("Segoe UI", 10)`）——字号差距要明显（1.6 倍以上），不要
   标题 14 正文 12 这种几乎看不出区别的对比。不要靠给每个区块加
   `relief="groove"`/`borderwidth` 之类的边框来区分层级，那样看起来更像
   Windows 98。全局字体统一用 `"Segoe UI"`（Windows 系统自带，比 Tkinter
   默认的 `"Segoe UI"`/`"MS Sans Serif"` 更现代，且不需要额外安装字体文件）。

6. **列表/表格类数据必须能看清结构**：用 `ttk.Treeview` 时要设置 `columns` 和
   `headings`，不要把所有字段拼成一个字符串塞进单列——用户要能看出"这是标题
   这一列，那是状态那一列"。

## 质量检查点
- [ ] 全程没有出现裸 `tk.Button`/`tk.Entry`/`tk.Listbox`（多字段列表场景下）
- [ ] 设置了 `ttk.Style().theme_use("clam")`
- [ ] 所有 padx/pady 是 8 的倍数
- [ ] 只有一个强调色用在主要操作按钮上
- [ ] 标题和正文字号差距明显（≥1.6 倍），不靠边框区分层级
