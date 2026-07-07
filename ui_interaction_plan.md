# UI 交互验证改造方案（ui_interaction_plan.md）

> 承接 [problem.md](problem.md) #52："截图/交互工具已经造好，但从未接入判断链路"。
> 目标：把 `frontend`/`ui_validate` 类型的验收标准从"LLM 读代码猜"改成"真实启动应用，
> 用 pywinauto 点一下、填一下、读一下控件真实状态"，判定结果来自确定性执行，不是猜测。

---

## 设计原则（讨论中定下来的几条，改动时不要违反）

1. **不需要视觉/识图能力**：全程不把截图喂给任何 LLM。控件状态（列表行数、文字内容）
   都是 pywinauto 直接问 Win32 UI Automation API 拿到的确定性结果，跟 DeepSeek 有没有
   识图能力无关
2. **"测什么"交给 LLM，"测得准不准"交给确定性代码**：LLM 读**真实生成出来的代码**
   （不是 FrontendExpert 自己写的一份清单——那样清单和代码可能对不上，是设计初稿里
   已经排除掉的一个坑）产出一份"交互测试计划"，Validator 照着计划真实执行、比对结果
3. **覆盖 CRUD 和纯查询两种模式**：操作后该看"列表行数变了"还是"某段文字变了"，
   由 LLM 判断，不是写死只支持一种
4. **第一版范围收窄**：只验证 `primary_action`（最核心的一个操作，通常是"添加"或
   "查询"），不做删除/编辑这类需要先选中已有行的更复杂交互——这类交互需要"先保证
   列表里有至少一条数据可选"这个前置条件，会跟 primary_action 的执行结果耦合，
   复杂度明显跳一档，留到验证过第一版真的有用之后再加

---

## 需要 LLM 输出的 JSON：逐行标注

这是新增的一次 LLM 调用（读 `code_content`，不读 FrontendExpert 的自述），要求输出：

```json
{
  "applicable": true,
  "reason_if_not_applicable": "",
  "inputs_in_order": [
    {"purpose": "城市名", "test_value": "北京"}
  ],
  "primary_action": {"button_text": "查询"},
  "output_check": {
    "widget_type": "label",
    "widget_order_hint": 2,
    "success_condition": "text_changes"
  }
}
```

逐行标注：

| 字段 | 类型 | 含义 | 下游怎么用 |
|---|---|---|---|
| `applicable` | bool | 这份代码有没有"填→点→看结果"这种能测的交互模式 | `false` 时直接跳过本项检查（不算失败，除非同时存在 `ui_validate` 类型验收标准，那种情况下"LLM 说没有可交互的东西"本身就是一条真实失败——代码大概率没把交互实现出来） |
| `reason_if_not_applicable` | str | `applicable=false` 时说明原因，`true` 时留空 | 只进日志，不参与判断，方便复核时看懂为什么跳过了 |
| `inputs_in_order` | list[object] | 按控件在代码里创建的先后顺序列出每个输入框 | 跟 `list_inputs(window)`（按界面实际创建顺序枚举 Entry 控件）按位置一一对应去填；LLM 必须按代码里出现的顺序列，不能乱序 |
| `inputs_in_order[].purpose` | str | 这个输入框是干嘛用的（从变量名/相邻 Label 文字猜出来） | 只进日志，不参与判断，纯粹给人看懂"填的是哪个字段" |
| `inputs_in_order[].test_value` | str | 真正会被敲进这个输入框的值 | 直接传给 `ui_input()`；LLM 要挑一个"符合这个用途、大概率不会被业务逻辑判定非法"的值（猜城市就填真城市，猜金额就填数字）——prompt 里要明确要求"填一个语义合理、大概率不会被业务逻辑当成非法输入拒绝的值"，不能随手编 |
| `primary_action.button_text` | str | 要点击的按钮上的文字，必须跟代码里 `text=` 参数完全一致 | 传给 `ui_click(window, button_text)`——按钮的可见文字是 pywinauto 唯一能可靠定位到它的信息 |
| `output_check.widget_type` | `"label"` 或 `"treeview"` | 操作后该看哪种类型的控件 | 决定调 `ui_get_text()`（label）还是 `count_list_rows()`（treeview） |
| `output_check.widget_order_hint` | int，仅 `widget_type=label` 时需要 | 这个 Label 在窗口所有 Label 控件里，从上到下数排第几个（从 1 开始） | 传给一个新增的 `list_labels(window)[order_hint - 1]` 去定位。**不用文字内容定位**——结果类 Label 通常操作前是空字符串（比如天气查询结果显示前是空的），拿"内容"去找一个"内容本来就是空"的控件，逻辑上是矛盾的，只有位置是操作前后都不变的稳定线索；`widget_type=treeview` 不需要这个字段（简单应用一般只有一个主列表） |
| `output_check.success_condition` | `"text_changes"` / `"text_non_empty"` / `"row_count_increases"` | 怎么判定这次操作"生效了" | `text_changes`：操作前后文字不一样；`text_non_empty`：操作后文字非空（用于本来就没有"操作前"基线的场景）；`row_count_increases`：操作后行数比操作前多 |

**`test_value` 可能不合法时的处理**：如果填入 `test_value` 后点击按钮，应用自己的校验逻辑报错/拒绝（比如弹出错误提示框、或者输出控件显示了一条错误信息而不是预期结果），这种情况**重新调用一次 LLM 换一版计划**（带上"上一版 test_value 触发了校验失败"这条反馈，类似 `backend_expert.py::_build_retry_feedback()` 的思路），最多重试 2 次；仍然失败就判定这条交互检查失败，不无限重试。

---

## 具体修改措施

### 1. `desktop_control.py` 新增三个工具函数
```python
def list_inputs(window) -> list:
    """按创建顺序返回窗口里所有 Entry 控件"""

def list_labels(window) -> list:
    """按创建顺序（从上到下）返回窗口里所有 Label 控件，配合 widget_order_hint 定位"""

def count_list_rows(window) -> int:
    """数一下 Treeview/Listbox 控件里当前有几行数据"""
```

### 2. `validator_prompt.py` 新增交互计划生成 prompt
新函数 `build_interaction_plan_prompt(code_content) -> str`，独立于现有的
`build_check_prompt()`（验收标准核对用的那个），不合并成一次调用——保持两个
prompt 各自单一职责，其中一个解析失败不会连累另一个（现有的验收标准核对是
已经跑通、稳定的路径，不想因为新功能牵连它）

### 3. `checkers.py` 新增 `ui_interaction_check()`
```python
def ui_interaction_check(app_path, code_content, criteria_task_type=None) -> Tuple[bool, List[str], List[FailedTest]]:
    # 1. 调用 build_interaction_plan_prompt，拿到计划
    # 2. applicable=false 时：存在 ui_validate 类型标准 → 记失败；否则跳过（不算失败）
    # 3. applicable=true 时：启动应用（复用 _launch_app，见下）
    #    → list_inputs() 按顺序填 inputs_in_order
    #    → 记录 output_check 指向控件操作前的状态
    #    → ui_click(primary_action.button_text)
    #    → 再读一次 output_check 指向控件的状态，按 success_condition 比对
    # 4. 失败项 task_type 统一记 "ui_validate"
```
第 4 点顺带确认了一件事：`task_type="ui_validate"` 的失败项，正好会命中今天早些时候
已经改好的 `should_retry` 里 `frontend_failed` 判断（`task_type in ("frontend",
"ui_validate")`），不需要再改 `workflow.py` 的路由逻辑——这条检查失败会自动正确触发
`FrontendExpert` 重试

### 4. 把启动逻辑重构成共享函数，不要写第二遍
`run.py::_launch_and_screenshot()` 里"启动 + 等窗口出现 + 处理 venv 转发桩 PID"那段
逻辑（已经踩过坑、验证过的部分）拆成一个 `_launch_app(app_path, logs) -> window`，
截图和交互检查都调用它，避免同一个应用启动两次（更慢，也更容易碰到窗口渲染时机不稳定
的问题）

### 5. 接进 `validate()` 主流程
`run.py::validate()` 调整步骤顺序：启动应用一次 → 交互检查（含操作前后的状态记录）
→ 截图（复用已经启动的同一个窗口，不重新启动）。`ui_interaction_check` 产出的失败项
并入 `all_failed`，跟其他四项检查一样汇总判定 `passed`

---

## 验收标准

- 用一个纯查询类应用（天气查询）和一个 CRUD 类应用（记账/待办）分别测一遍，确认
  `output_check.widget_type` 两种取值都能正确执行判定
- 构造一个"点击按钮但控件状态没变化"的场景，确认 `ui_interaction_check` 能判定
  失败且失败项 `task_type="ui_validate"`，并且确认这会正确触发 `FrontendExpert` 重试
  （不需要改路由代码，只是确认这条链路真的接上了）
- `applicable=false` 场景：构造一个没有表单/按钮的纯静态展示代码，确认不会被误判为失败
- 确认应用只被启动一次（不是截图一次、交互检查再启动一次）
