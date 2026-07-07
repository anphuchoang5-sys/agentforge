# 重试路由改造方案（retry_update.md）

> 承接 [problem.md](problem.md) #21："重试闭环只会回头改 BackendExpert"。
> `failed_tests[].task_type` 归因已经做完并验证（见下方"现状"），本文档是下一步——
> 用这个标签让重试真正修到问题所在，而不是死磕同一个跟问题无关的地方。

---

## 背景：这个问题长什么样

todo 应用曾经真实复现过：Validator 判定失败的原因是"每个事项没有独立的完成/删除按钮"
（`app.py`，FrontendExpert 的产出），但 `workflow.py` 的重试边写死只回 `backend_expert`。
连续 4 轮重试，`BackendExpert` 反复重写一个跟按钮布局毫无关系的 `db.py`，`app.py`
从第 0 轮到第 3 轮字面意思完全没变，5 轮用完直接放弃。

---

## 现状：已经做完并验证的部分

`failed_tests` 里每一条失败项现在都带 `task_type`（`"backend"` / `"frontend"` / `"test"` /
`"ui_validate"` / `None`），来源：

- Commander 拆解需求时给每条 `acceptance_criteria` 标了归属（`SubTask.type`）
- `workflow.py::validator_node` 构造 `criteria_task_type: dict[str, str]`（验收标准原文 →
  任务类型），经 `validator_stub.py` → HTTP/直连两条路径 → `checkers.py::llm_check()`
  用**精确字符串匹配**查回归属，不依赖 LLM 自己猜
- `compile_check` / `ruff_check` / `pytest_check` 三项检查产生的失败项 `task_type` 保持
  `None`——它们不是从某条验收标准来的，标不出来不该硬猜

已用真实数据验证：同一次 `validate()` 调用里，`frontend` 类型和 `test` 类型的失败可以
同时出现在 `failed_tests` 列表里，互不覆盖，前后端同时出问题时**打标签这层没有问题**。

**没做的部分**：`should_retry` 完全不看 `failed_tests` 的 `task_type`，永远只输出
`"backend_expert"`。诊断报告已经能准确说出病根在哪，但治疗方案还没接上诊断结果。

---

## 方案：backend 打底，frontend 按需追加

**核心设计**：重试时 `backend_expert` 永远触发（不管这轮是不是它的锅），`frontend_expert`
只有在 `failed_tests` 出现 `task_type in ("frontend", "ui_validate")` 时才**追加**触发。
**永远不会出现"只重试 frontend_expert"的情况。**

这个设计换来一个重要简化：`backend_expert → test_expert` 这条边现在、以后都只会被触发一次，
不需要给 `frontend_expert` 新增任何出边——彻底避开"两条边汇入同一节点被触发两次"这个已经
踩过一次的坑（validator 那次的教训，见 [workflow.py](backend/graph/workflow.py) 里那段
关于 LangGraph Pregel/BSP superstep 的长注释），也不用去解决"frontend_expert 单独重试时
谁来触发 test_expert"这个更难的问题。

代价：`backend_expert` 没问题时也会被拉着重新生成一次，多花一次 LLM 调用；但正确性不受
影响（BackendExpert 的 prompt 除了失败反馈没变，多半生成类似代码），比"5 轮都在改错地方"
划算得多。

---

## 具体步骤

### 第 0 步（先做，不动真图）：验证 LangGraph 条件边能否一次路由到多个节点

写一个独立的四节点玩具图，确认：

1. 路由函数直接返回 `["backend_expert", "frontend_expert"]`（不经过 `path_map` 字典）时，
   两个节点是否真的在同一个 superstep 被触发
2. 只返回 `["backend_expert"]` 单元素列表时是否照常工作（保证不破坏现在"只重试 backend"
   这个最常见情况）
3. 模拟的下游节点（对应 `test_expert`）是否真的等两个上游都跑完才执行——这一条其实已经
   有把握（Pregel/BSP 的 superstep 屏障，`decompose → {backend_expert, frontend_expert} →
   test_expert` 现在的主链路已经在依赖这个行为），玩具图跑一遍是复核，不是从零验证

**这一步跑不通就走文末的"退化方案"。**

### 第 1 步：`should_retry` 改造 —— [workflow.py](backend/graph/workflow.py)

```python
def should_retry(state: ProjectState) -> list[str] | str:
    if state.get("validation_passed"):
        return END
    if state.get("iteration_count", 0) >= 5:
        return END

    failed = state.get("failed_tests") or []
    frontend_failed = any(f.get("task_type") in ("frontend", "ui_validate") for f in failed)

    targets = ["backend_expert"]
    if frontend_failed:
        targets.append("frontend_expert")
    return targets
```

`add_conditional_edges` 相应改成不传 `path_map`（前提是第 0 步验证可行），路由函数直接
返回真实节点名或 `END`。

### 第 2 步：`_build_retry_feedback()` 按 `task_type` 过滤 —— [backend_expert.py:98](backend/agents/experts/backend_expert.py:98)

现状：这个函数把 `failed_tests` 全部塞给 BackendExpert，注释原话是"不去猜哪条该过滤
（problem.md 第42条：目前的数据结构猜不准哪条标准属于哪个专家），全部给模型看"——这段
注释描述的问题已经被 `task_type` 解决了，该更新。

```python
reasons = "\n".join(
    f"- [{f.get('name', '?')}] {f.get('reason', '')}"
    for f in failed_tests
    if f.get("task_type") not in ("frontend", "ui_validate")
)
```

过滤原则是"明确知道不是自己的锅才跳过"，不是"只挑明确是自己的"——`task_type=None` 的
`compile`/`ruff`/`pytest` 失败项照样要给 BackendExpert 看，标不出类型不代表跟它无关。

### 第 3 步：给 `frontend_expert.py` 建一份同款 `_build_retry_feedback()`

`frontend_expert_node` 目前完全不读 `state["failed_tests"]`，需要照抄 `backend_expert.py`
的结构从零建一份，过滤条件相反：跳过 `task_type in ("backend", "test")` 的项。不加这一步，
就算路由修对了，`frontend_expert` 拿到的还是跟第一次一模一样的 prompt，等于白重试。

### 第 4 步：`event_translator.py` 的"第几轮修复"计数联动

`_on_frontend_expert` 现在没有 `_on_backend_expert` 那套"是不是第一次调用"的判断（因为以前
`frontend_expert` 只会调用一次）。改造后它可能在重试轮次里再次触发，需要照抄同款计数逻辑，
否则前端日志看不出这一轮到底是谁在修。

---

## 验收标准

- **只有 backend 失败**的场景：确认只重试 `backend_expert`，行为跟现在完全一致（不能因为
  改造引入回归）
- **只有 frontend 失败**的场景：确认 `backend_expert` 依然被打底触发，`frontend_expert`
  被追加触发，且 `frontend_expert` 拿到了带着失败原因的新 prompt
- **前后端同时失败**的场景：确认两个专家都被触发，且各自 prompt 里的反馈是各自类型对应
  的失败项，不是混在一起的大杂烩
- 用之前 todo 应用"每项独立按钮"的真实失败场景重新跑一遍，确认这次不会 5 轮都卡在同一
  个地方

---

## 退化方案（第 0 步验证多目标路由不可行时）

`should_retry` 每轮只返回一个目标：优先看有没有 backend 类型失败，有就修 backend；没有
backend 只有 frontend 失败才单独修 frontend。但这样要接受"frontend_expert 单独跑完，谁
触发 test_expert"的问题，需要额外加一条 `frontend_expert → test_expert` 边，且要重新
验证这条新边不会在未来改动里重复触发 test_expert。效果上从"一轮修完"退化成"最多两轮
修完"，但比现在"5 轮都在死磕同一个地方"已经是明显改善。
