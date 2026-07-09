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
- [ ] 会触发状态变化的主操作按钮（添加/删除/查询/确认等）用的是 `tk.Button`，
      不是 `ttk.Button`
- [ ] 会被验证读取数值变化的结果类 Label 用的是 `tk.Label`，不是 `ttk.Label`
- [ ] 除上述两类例外，其余控件（Entry/Frame/Combobox/Spinbox/Treeview）保持
      `ttk`，没有被顺手改成裸 `tk`
- [ ] 设置了 `ttk.Style().theme_use("clam")`
- [ ] 所有 padx/pady 是 8 的倍数
- [ ] 只有一个强调色用在主要操作按钮上
- [ ] 标题和正文字号差距明显（≥1.6 倍），不靠边框区分层级
