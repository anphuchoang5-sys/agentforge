# 已知问题清单

> 记录当前实现和文档承诺之间的落差，不是待办事项列表，是"诚实记账"——
> 方便后续决定哪些要补、哪些接受现状、哪些要改文档降低承诺。
> 更新日期：2026-07-03

---

## 核心问题：动态编排是假的

**现象**：Commander 的输出（`TaskDecomposition`）长得像一张动态 DAG——有依赖关系、
有验收标准、有预估迭代次数，但 `workflow.py` 的执行图是 B 手写死的固定流水线
（`decompose → backend/frontend → test → validator → 重试`），不读取、不响应
Commander 生成的任何调度信息。

**结论**：现在不是"AI 自主编排任务"，是"AI 填一份好看的说明书，B 写死的剧本照演"。
下面所有"生成了但没人用"的字段，根源都是这一条。

---

## 具体问题清单

### 1. `SubTask.dependencies` 生成了但从未被读取
- **在哪**：`commander_prompt.py` 教 AI 给每个任务标依赖关系（如 `test` 依赖 `backend`）
- **实际情况**：`workflow.py` 的节点连接是硬编码 `add_edge(...)`，不读这个字段
- **状态**：未修复。今天已经把 prompt 里"test 无依赖"这处内容错误对齐成"test 依赖 backend"，
  但这只是让**生成的数据更准确**，没有让**执行引擎去读它**

### 2. `SubTask.acceptance_criteria` 生成了但从未被使用
- **在哪**：每个任务都带一份验收标准，设计给 Validator 逐条比对
- **实际情况**：`validator_stub.py` 的 Mock 实现只检查"文件存在+测试无FAILED"，
  完全不读 `task_decomposition`，看不到验收标准
- **状态**：未修复，等 C 实现真实 Validator 时需要一并接上

### 3. `TaskDecomposition.estimated_iterations` 生成了但从未被使用
- **在哪**：AI 自己估计需要几轮修复
- **实际情况**：重试上限固定写死 `iteration_count >= 5`，不看这个估计值
- **状态**：未修复

### 4. `ui_validate` 任务类型生成了，但图里没有对应节点
- **在哪**：`commander_prompt.py` 规定"只有 ui_validate 依赖 frontend"，会生成这类任务
- **实际情况**：`workflow.py` 里没有任何节点处理这个类型，等 C 做出 UIValidator Agent 才会用上
- **状态**：预期内的"占位"，不算 bug，但目前完全空转

### 5. 同类型的第 2、3 个任务会被静默丢弃
- **在哪**：`backend_expert_node`/`frontend_expert_node` 筛出同类型任务后，
  只取 `[0]`（第一个），假设 Commander 每种类型只生成一个任务
- **实际情况**：Pydantic schema 没有强制"每种 type 只能一个"，AI 若一次生成多个同类型任务，
  后面的会被无声吞掉，没有报错、没有日志
- **状态**：已知风险，暂不处理（讨论后认为现阶段影响小）

### 6. `skills/` 下三个 SKILL.md 完全没被运行时加载
- **在哪**：`backend/skills/{build,test,spec}/SKILL.md`，对齐 CLAUDE.md
  "Skills集成：调用对应Skill保证代码质量"这条职责
- **实际情况**：全项目搜索，除了 `output_naming.py` 里一句注释提了一下文件名，
  没有任何代码在运行时读取/加载这些文件。各专家 Agent 的 System Prompt
  都是硬编码在对应 `.py` 文件里的字符串，跟 SKILL.md 毫无关联
- **状态**：未修复，Skills 层目前只是静态文档，不是生效机制

### 7. 完全没有记忆持久化
- **在哪**：CLAUDE.md 设计了 mem0 + ChromaDB + LangGraph MemorySaver 三层记忆
- **实际情况**：全项目搜索 `checkpointer`/`MemorySaver`/`chromadb`/`mem0`，零命中。
  `graph.compile()` 没传 `checkpointer`，`run()` 每次调用完全无状态，
  上一次生成过什么、失败过什么，下一次调用完全不知道
- **状态**：CLAUDE.md 里标为"选做"，Week 2 才计划做，不算失职，但目前是彻底的空白，
  不是"简化版"，是"完全没有"

### 8. FastAPI API 层不存在
- **在哪**：CLAUDE.md 设计了 `POST /api/tasks`、`WS /ws/tasks/{id}` 等接口，
  是"必做"项，D 的前端预期通过这层接真实数据
- **实际情况**：`backend/api/` 目录不存在，`run()` 只能当裸 Python 函数直接调，
  D 现在的前端只能用 Mock 数据，没有真实接口可接
- **状态**：未开始，是目前唯一还没人碰的"必做"项，比记忆缺失更影响能不能演示

### 9. Commander 曾建议前端技术栈，与 FrontendExpert 写死的 Tkinter 冲突
- **状态**：✅ 已修复（07-03）。`commander_prompt.py` 加了规则：
  description 只讲功能，不建议具体技术栈

### 10. `test_expert.py` 完全不读 Commander 给的 test 任务描述
- **状态**：✅ 已修复（07-03）。现在会读 `type=="test"` 任务的 description，
  跟 backend_expert/frontend_expert 统一了模式

### 11. CLAUDE.md 里 OpenClaw"幻觉项目"的错误结论
- **状态**：✅ 已修复（07-03）。OpenClaw 真实存在，已勘误 CLAUDE.md 三处 +
  系统架构.html 的 AI 模型层（同时把 Ollama-only 改成 DeepSeek 优先+Ollama兜底，
  对齐实际代码）

---

## 待决策事项

- **要不要把动态调度真的做出来**：让 `workflow.py` 根据 `task_decomposition.tasks`
  和 `dependencies` 动态搭图，而不是写死固定流水线。工作量不小，两周工期内是否值得，
  还是接受现状、在文档里降低"动态编排"这个说法的承诺程度，说清楚现在是简化版
- **Skills 层要不要真的接上**：让专家 Agent 的 System Prompt 从 SKILL.md 读取而不是硬编码，
  还是干脆承认现在不需要这层抽象，把 SKILL.md 当纯文档留着就好
- **记忆层和 API 层谁先做**：API 层是必做项且直接影响能否演示，优先级应该更高
