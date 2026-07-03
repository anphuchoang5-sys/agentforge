# 已知问题清单

> 记录当前实现和文档承诺之间的落差，不是待办事项列表，是"诚实记账"——
> 方便后续决定哪些要补、哪些接受现状、哪些要改文档降低承诺。
> 更新日期：2026-07-03（晚间修订：API 层 + 真实 Validator 已接入）

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
- **状态**：✅ 已修复（07-03 晚间）。`workflow.py::validator_node()` 从
  `task_decomposition.tasks[].acceptance_criteria` 拍平取出清单，传给
  `validator_stub.py::validate(criteria=...)` 再转发给 C 的 `llm_check()`。
  真实测试过：LLM 逐条核对代码、引用具体行号，还真的判过一条"界面美观易用"
  没完全达标（`passed: False`），会触发重试闭环——不是摆设了

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
- **状态**：✅ 已修复（07-03）。`backend/api/`（`POST /api/submit` + `WS /ws/tasks/{id}`
  + `GET /api/metrics/tokens`）+ `run(on_event=...)` 流式支持，D 的前端已从 Mock
  切换为真实数据，端到端验证过多轮

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

### 12. Token 消耗全程没有真实记录
- **在哪**：A 写了 `call_log.py` 的完整落盘机制，但 B 的三个专家 Agent 直接用
  `ChatOpenAI.invoke()`，从没调过 `log_call()`
- **状态**：✅ 已修复（07-03）。新增 `backend/tools/llm_logging.py::timed_invoke()`
  包一层，三个专家节点接入；顺手发现并修了 `call_log.py::get_recent_logs()`
  的真实 bug（对 `fetchall()` 结果又取 `.description`）。Commander 走的是
  `ollama_client.generate()`（不是 `ChatOpenAI`），暂未接入这套记录，图表里
  Commander 一栏目前还是空的

### 13. C 的真实 Validator 接入
- **状态**：✅ 已修复（07-03 晚间）。`pywinauto` 装了、`ruff` PATH 修了、C 的
  `server.py` 里 emoji 打印导致 Windows GBK 控制台崩溃的问题绕过了（`PYTHONIOENCODING=utf-8`，
  没改她代码）。C 后来自己把 `validator_stub.py` 改成"直接 Python 调用优先"，
  不再需要单独起 HTTP 服务，验证过真实启动应用+截图+ruff 检查全部工作正常

### 15. Commander 生成的验收标准可能跟专家的固定技术约束互相矛盾
- **在哪**：接上真实验收标准核对（第2条）后，用"骰子小游戏"需求实测发现——
  Commander 生成了"历史记录存储在内存中，重启后丢失"这条标准，但
  `BackendExpert` 的 System Prompt 里硬性要求"数据库文件名固定为 app.db"
  （必须 SQLite 持久化），两者互相矛盾
- **实际情况**：这条标准物理上不可能通过，但 `should_retry` 不知道"这轮失败是因为
  不可能达成"还是"这轮失败是因为代码写错了"，于是把 5 轮重试全部烧完
  （`iterations: 5`），每轮都要真实调用 DeepSeek API，最后依然 `validation_passed: false`。
  同一次测试里前端还有个键名不一致的真 bug（`db.py` 有时返回 `points` 有时 `value`，
  和 `app.py` 读的 `point`/`points` 对不上），这个是可以被修复轮次修好的，
  跟"内存存储"这条不可能修好的标准混在一起，进一步拖累收敛
- **状态**：✅ 已修复（07-03）。`BACKEND_SYSTEM_PROMPT` 去掉"数据库文件名固定为 app.db"
  的硬性要求，改成"任务要求持久化就用 sqlite3，要求内存存储就用普通变量"，
  让 `BackendExpert` 根据任务描述自己判断，不再跟这类验收标准结构性矛盾

### 17. TestExpert 真实跑过的 pytest 结果，从未被传到 C 的验证流程里
- **状态**：✅ 已修复（07-03 深夜）。三处一起改：① `test_expert.py` 的 pytest 命令加
  `--json-report --json-report-file=pytest_report.json`，路径存进新增的
  `state["pytest_report_path"]`；② `validator_stub.py`/`workflow.py::validator_node`
  转发这个路径；③ C 的 `checkers.py::pytest_check()` 从桩函数改成真的解析 JSON 报告，
  提取失败用例的具体断言信息。真实验证过：正确读出"27个测试，23通过，4失败"，
  还抓到一个真实 bug（自增 ID 计数器没有在测试间重置）

### 16. C 读取代码做 LLM 核对时有 8000 字符截断，长文件的测试标准验证不了
- **状态**：✅ 已修复（07-03 深夜）。C 的 `run.py::validate()` 加了可选参数
  `code_content`，`workflow.py::validator_node` 把 `state` 里已经完整存在、
  从没被截断过的 `backend_code`/`frontend_code`/`test_code` 拼好直接传过去，
  不用 C 再重新读硬盘+截断。真实验证过：17102 字符完整传递，LLM 能同时看到
  db.py 和 test_app.py 的完整内容，不再出现"文件被截断"

### 14. `ollama_client.py` 文件名具有误导性
- **在哪**：`backend/agents/commander/ollama_client.py`——早期纯 Ollama 架构的历史命名，
  DeepSeek 迁移后内部逻辑已经是 DeepSeek 优先，但文件名没跟着改，容易让人误以为
  还在用 Ollama（今天已经被问到一次）
- **状态**：不修——本人评估过，改名涉及全项目 import 路径，风险大于收益，暂缓

---

## 待决策事项

- **要不要把动态调度真的做出来**：让 `workflow.py` 根据 `task_decomposition.tasks`
  和 `dependencies` 动态搭图，而不是写死固定流水线。工作量不小，两周工期内是否值得，
  还是接受现状、在文档里降低"动态编排"这个说法的承诺程度，说清楚现在是简化版
- **Skills 层要不要真的接上**：让专家 Agent 的 System Prompt 从 SKILL.md 读取而不是硬编码，
  还是干脆承认现在不需要这层抽象，把 SKILL.md 当纯文档留着就好
- ~~记忆层和 API 层谁先做~~：API 层已完成，记忆层仍是 Week2 选做，暂不处理
- **`estimated_iterations` 要不要接进重试上限**：现在固定 5 轮硬顶。如果要让
  Commander 的估计值生效，得想清楚是"软目标+5轮硬顶不变"还是真的动态改上限——
  后者有被 AI 估计值带偏、失去安全网意义的风险，偏向前者但还没定
