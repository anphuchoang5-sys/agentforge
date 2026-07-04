# 已知问题清单

> 记录当前实现和文档承诺之间的落差，不是待办事项列表，是"诚实记账"——
> 方便后续决定哪些要补、哪些接受现状、哪些要改文档降低承诺。
> 更新日期：2026-07-04（新增：Commander/Validator Token 记账接入 + 两轮全仓库代码审查；
> 修复：#27 validator_stub 静默造假 / #28 WebSocket 单消费者卡死 / #29 run() 异常处理与空交付物 /
> #31 GBK 控制台崩溃）

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
- **状态**：✅ 已修复（07-03 三个专家；07-04 补上 Commander + Validator）。
  新增 `backend/tools/llm_logging.py::timed_invoke()` 包一层，三个专家节点接入；
  顺手发现并修了 `call_log.py::get_recent_logs()` 的真实 bug（对 `fetchall()`
  结果又取 `.description`）。Commander 和 Validator 走的是 `ollama_client.generate()`
  （不是 `ChatOpenAI`），当时暂未接入——07-04 把 `decompose.py` 的两条 LLM 调用
  路径（结构化输出 + JSON 兜底）和 `checkers.py::llm_check()` 都换成
  `generate_with_metrics()` + `log_call()`，真实调用验证过：`by_caller` 里
  `commander`/`validator` 两栏都有真实 Token 数据了。测试产生的记账数据已清理，
  不会污染正式演示的图表

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

### 18. 系统当前是"一次性执行"，没有任何跨次记忆（#7 的产品视角复述）
- **在哪**：跟 #7 是同一个技术缺口（mem0/ChromaDB/LangGraph MemorySaver 全部缺失），
  这条只是换个角度把"这意味着什么"说清楚，不是新发现
- **实际情况**：不是"记忆功能弱"，是"完全不存在"。同一个需求跑两次，会得到两份
  互不参考的独立代码；上一次运行踩过的坑、用户提过的偏好，这一次运行**不知道**。
  一次运行内部因验证失败触发的"重试"，用的也只是这次运行 `state` 里现成的信息，
  不是从历史里学的。跟 CLAUDE.md 里"AI 软件工厂"这个定位对比，"工厂"暗示的
  持续学习/复用能力目前是 0，更准确的说法是"一次性代码生成器"
- **状态**：CLAUDE.md 已标为 Week2 选做，不算失职，但演示/汇报时应该说清楚这一点，
  不要让人误以为系统有跨会话学习能力

---

## 代码审查（2026-07-04）：死代码 / 重复逻辑 / 逻辑错误 / 安全漏洞

> 全仓库 41 个 backend .py 文件逐一过了一遍，只报有 file:line 证据的真实发现，
> 不报主观风格类意见。

### 19. 确认零调用的死代码
- **在哪**：
  - `backend/mcp_tools/desktop_control.py` 的 `app_close()` / `app_connect()` / `launch_and_get_window()`
  - `backend/agents/commander/ollama_client.py` 的 `generate()`（含私有的 `_generate_deepseek()`/`_generate_ollama()`）
  - `backend/agents/commander/decompose.py` 的 `decompose_with_metrics()`
  - `backend/agents/commander/call_log.py` 的 `get_stats()`
  - `backend/agents/validator/schemas.py` 的 `PASS_REPORT_TEMPLATE`
  - `backend/agents/validator/__init__.py` 里的 `fastapi_app` 再导出
- **实际情况**：全部经过全仓库 grep 确认零调用方（不只是同文件内，是整个 `backend/` 树）。
  两处值得单独说明：① `generate_with_metrics()` 内部自己重新实现了一遍 DeepSeek/Ollama
  分支逻辑，没有复用 `generate()`，导致 `generate()` 完全没人用却一直留着；
  ② `fastapi_app` 这个别名本身没人 import，但 `validator_stub.py` 用
  `from backend.agents.validator import validate` 会触发整个包初始化，导致每次
  生产环境跑真实验证流程都顺带执行 `server.py`、构建一整个 FastAPI app 对象，
  只是为了让这个没人用的别名存在——不是"编译时死代码"，是"运行时真实执行但
  产出物没人用"的浪费
- **状态**：未修复，建议清理但不紧急，不影响功能

### 20. 三处专家 Agent 之间的重复逻辑
- **在哪**：`_extract_code()` 在 `backend_expert.py`/`frontend_expert.py`/`test_expert.py`
  里逐字节相同；`ChatOpenAI(...)` 客户端构造三处几乎相同（只有 temperature 不同：
  0.2/0.2/0.1）；`api_spec_text` 拼接逻辑在 `backend_expert.py`/`frontend_expert.py`
  里相同；另外 JSON-from-markdown 提取逻辑在 `decompose.py::_parse_json_fallback()`
  和 `checkers.py::llm_check()` 里各自独立实现了一遍，做同一件事但健壮性不同
  （前者会扫描 `{`/`}` 边界兜底，后者没有）
- **实际情况**：三个专家的重复是"专家 Agent 独立可维护"这个设计本身的代价，不是
  这次审查才产生的新问题——好处是改一个专家不会牵连另外两个，坏处是
  `_extract_code()` 这类解析逻辑如果发现一个 markdown 围栏解析的边界 bug，
  需要在三个文件里分别修，改漏一个不会报错，只会在特定场景悄悄用旧逻辑
- **状态**：已知设计取舍，暂不处理三个专家的重复；两处 JSON 解析器不统一算是
  可以顺手统一的小项，优先级不高

### 21. `workflow.py` 的重试逻辑存在两个实质问题（本次审查最值得优先看的一条）
- **在哪**：`backend/graph/workflow.py` 的 `count_iteration`/`should_retry`
  （约71-80行）和失败后的条件边路由（约136-143行）
- **实际情况**：
  ① **迭代次数比文档少一次**：`count_iteration` 在**第一次**验证（不是重试，
  是第一次跑）之后就已经 `+1`，`should_retry` 在 `iteration_count >= 5` 时停止——
  实际效果是"第一次尝试 + 4 次重试"，不是文档/`project_state.py` 字段注释里
  写的"最多重试 5 次"。少了一次真实的修复机会，不报错，只是安静地比设计值少跑一轮。
  ② **重试只会回头改 BackendExpert，FrontendExpert 永远不会被重新触发**：
  失败后的条件边只指回 `"backend_expert"`，`FrontendExpert` 只在第一轮跑一次
  （从 `decompose` 那条边进来），之后所有重试都只重新生成后端代码。如果
  Validator 判定失败的原因出在前端（界面缺元素、验收标准是关于 UI 的），
  接下来最多 4 轮重试全部在修一个跟问题无关的地方，前端的真实 bug 在 5 轮
  预算内永远没有机会被修复。代码里现有注释只论证了"为什么不会被 LangGraph
  的 superstep 机制抢跑"，没有覆盖"前端类 bug 结构性修不好"这个问题
- **状态**：未修复，直接影响"闭环自动修复"这个核心卖点在前端 bug 场景下的有效性

### 22. `validate()` 对空字符串路径的判断，跟"不许静默兜底"的架构原则冲突
- **在哪**：`backend/agents/validator/run.py`/`checkers.py` 里用
  `Path(app_path).exists()`/`.is_dir()` 判断路径是否存在，`workflow.py::validator_node`
  传入的是 `state.get("frontend_path", "")`
- **实际情况**：Python 的 `Path("").exists()` 和 `.is_dir()` 都返回 `True`
  （pathlib 把空字符串当成当前目录 `.`），所以如果 `frontend_path` 万一是空字符串
  （正常流程下 LangGraph 的 superstep 机制应该保证不会是空，代码注释里也是这么
  论证的），`read_app_code("")` 不会报错，而是会静默去**进程当前工作目录**扫
  最多 10 个 `.py` 文件当成"要验证的代码"去读——这跟 CLAUDE.md 明确写的
  "任何模块失败必须抛出明确异常，禁止返回写死的假数据/静默兜底"这条架构原则
  直接冲突。目前推断是不会触发的边界情况（不是已确认复现的 bug），但防御性
  判断本身写错了：`if not Path(app_path).exists()` 看起来像是在防"路径不存在"，
  实际完全防不住"路径是空字符串"这种情况
- **状态**：未修复，风险等级"目前推测不会触发"，但值得加一行"path 为空直接 raise"

### 23. `task_manager.py` 的任务字典没有回收机制，长期运行会内存泄漏
- **在哪**：`backend/api/task_manager.py` 的 `_tasks` 字典和 `_background_refs`
  集合（约33-40行）
- **实际情况**：任务完成后只是把 `task.done` 标记为 `True`，字典里的 Task 对象
  （包含它完整的事件队列）永远不会被删除。两周演示项目里跑几次、几十次不会有
  感知，但如果这个 API 服务器长期运行，每提交一次任务就永久占用一份内存，
  没有过期清理或大小上限
- **状态**：未修复，两周演示阶段优先级低，长期部署前需要加

### 24. 安全漏洞：MCP 暴露的 `run_command` 是无沙箱命令注入面
- **在哪**：`backend/tools/command_tools.py` 的 `run_command()`，经
  `backend/mcp_tools/mcp_server.py` 的 `tool_run_command` 暴露给 MCP 客户端
- **实际情况**：`subprocess.run(cmd, shell=True, ...)`，`cmd` 是调用方传入的原始
  字符串，没有白名单、没有转义，不限制 `;`/`&&`/`|`/反引号等 shell 元字符。
  当前项目内唯一真实调用方（`test_expert.py`）传的是写死的命令字符串，不是
  LLM 生成的内容，所以现在跑的这条流水线本身不会被这个口子直接打穿；但这个
  工具作为 MCP Server 能力，**本身就是设计成能被任何 MCP 客户端（包括 LLM
  驱动的 agent）调用的**，一旦未来有任何环节让 LLM 输出的内容流入这个 `cmd`
  参数，就是一个完整的远程代码执行洞——不是"理论风险"，是"目前没人恰好
  触发，但设计上完全没有防护"
- **状态**：未修复，建议至少加白名单（只允许 `python`/`pip`/`pytest` 等固定
  前缀命令）或改用 `subprocess.run(shlex.split(cmd), shell=False)` 去掉 shell 解释层

### 25. 安全漏洞：MCP 暴露的 `read_file`/`write_file` 没有目录穿越防护
- **在哪**：`backend/tools/file_tools.py` 的 `write_file()`/`read_file()`，经
  `mcp_server.py` 的 `tool_write_file`/`tool_read_file` 暴露
- **实际情况**：只做了 `os.path.abspath(path)`（会解析掉 `..`，但不会把结果
  限制在任何基准目录内），然后直接对这个绝对路径读写，没有任何白名单校验。
  调用方理论上可以传 `"../../.env"` 或 `"C:\\Users\\...\\.env"` 这种路径，
  读到 `.env` 里的 `DEEPSEEK_API_KEY`，或者覆盖仓库外任意可写文件。目前流水线
  里的真实调用方（三个专家节点）传的路径都是基于经过清理的 `app_output_dir`
  拼出来的，所以现在的主链路是安全的；但这两个工具作为通用能力暴露在 MCP 层，
  没有任何"关"在预期目录里的机制。另外 `backend/api/routes/tasks.py` 的
  `POST /api/submit` 对 `user_input` 也没有长度上限/内容校验，属于同一类
  "网络入口缺纵深防御"，不过因为落地文件名会经过 `_sanitize_app_name` 清理，
  暂不算可直接利用
- **状态**：未修复，建议给 `read_file`/`write_file` 加一个"结果路径必须在指定
  base_dir 之内"的校验（`Path(base_dir).resolve()` 后检查 `is_relative_to`）
- **附注**：全仓库 grep 未发现 `eval`/`exec`/`pickle`/字符串拼接 SQL；
  `call_log.py` 全程用 `?` 占位符参数化查询，没有 SQL 注入风险；`shell=True`
  仅此一处

### 26. `call_log.py` 的 `LOG_DB_PATH` 路径计算错误：日志库落在了仓库外面
- **在哪**：`backend/agents/commander/call_log.py` 第17行，
  `LOG_DB_PATH = Path(__file__).parents[4] / "data" / "call_logs.db"`
- **实际情况**：`call_log.py` 位于 `backend/agents/commander/call_log.py`，
  `parents[3]` 才是项目根目录（`commander→agents→backend→项目根`，对应
  `parents[0..3]`），`parents[4]` 是再往上一级。在这台机器上实际解析成了
  `E:\data\call_logs.db`，完全在 git 仓库之外。不是"理论上可能出错"——今天
  为了清理本轮测试产生的记账数据时，实际验证了 `LOG_DB_PATH.exists()` 为
  `True` 且路径确实是 `E:\data\call_logs.db`，说明这个项目从有这个文件开始，
  所有调用记录事实上一直被写在仓库外面，只是因为这台机器 E 盘根目录恰好
  可写、恰好没人去检查这个路径，才没有被发现
- **实际影响**：换一台机器、换一个盘符、或者按 CLAUDE.md 规划用 Docker
  部署，这个路径要么指向一个完全不相关或不存在的目录，要么在容器里指向
  跟仓库无关的路径——`data/` 目录本该是仓库内可被 `.gitignore` 管理、可被
  打包进部署产物的一部分，现在实际上完全脱离了项目目录树
- **状态**：未修复，改法直接：`parents[4]` 改成 `parents[3]`

---

## 代码审查第二轮（2026-07-04）：API 并发层 / 完整状态机 / 桌面自动化 / 异常吞噬 / 测试覆盖

> 第一轮审查完 `tools/`、`mcp_tools/`、`commander/`、`experts/`、`validator` 的
> checkers/run/schemas 之后，这一轮补上还没细看的部分：`backend/api/` 全部、
> `workflow.py`/`pipeline/run.py` 完整状态机、`validator/server.py`/`_selftest.py`、
> `output_naming.py` 边界情况、全仓库"静默吞异常"模式排查、测试覆盖率现状。
> 下面每一条都经过本人二次核对源码确认，不是子任务报告直接照抄。

### 27. `validator_stub.py` 静默吞掉 C 的真实验证异常，兜底成一个能编造"通过"的假 Mock（本次审查最严重的一条）
- **在哪**：`backend/agents/validator_stub.py` 第41-52行（策略1：直接调 C 的
  `validate()`）和第57-67行（策略2：HTTP 调用），两处都是
  `except Exception as e: print(...)`，没有 `raise`，直接往下走到策略3
- **实际情况**：如果 C 的真实 `validate()` 出现的是一个**真实的代码 bug**（不是
  "环境不可用"这种可以理解的降级理由），这段代码会把这个异常当成"C 不可用"
  处理，吞掉之后掉进策略3——一个只做"文件存不存在" + "test_results 文本里有没有
  出现'failed'/'error'这几个字"的简陋 Mock，最后返回 `passed: True` 都是可能的。
  `problem.md` 第13条已经确认 C 后来把 HTTP 服务那条路径（策略2）废弃了，所以
  一旦策略1 抛出任何异常，现在**直接就落到这个能编造"通过"结果的 Mock 上**。
  `workflow.py` 的 `should_retry` 完全信任 `validation_passed` 这个字段来决定
  "要不要继续重试"——如果这个字段是被 Mock 假造出来的 `True`，重试循环会
  提前终止，向上游报告"验证通过"，但代码可能压根没被真的验证过
- **为什么这条最严重**：CLAUDE.md 的架构决策记录里明确写了"任何模块在失败时
  必须抛出明确的异常，禁止返回写死的假数据"，理由是"硬编码兜底会让调用方
  误以为成功，导致下游模块用错误数据继续运行，问题难以排查"——这条恰好
  精确踩中了这个原则本来要防的场景，而且踩在"验证结果"这个最不该出错的
  环节上
- **状态**：✅ 已修复（07-04）。策略1 的 `except Exception` 收窄成
  `except ImportError`——只在"C 的模块导入失败"（环境没装好）时才降级到
  策略2/3；一旦导入成功，真正调用 `c_validate(...)` 不再包在任何
  try/except 里，业务异常会原样往上抛，一路传到 `run()`（#29 已经记录
  `run()` 自己也不吞异常）、最终被 `task_manager.py` 的 `try/except`
  转成 `{"type":"error",...}` 事件让前端看到真实失败，不会再被静默
  改写成 Mock 编出来的 `passed: True`。策略2 同理，把 `except Exception`
  收窄成 `except requests.RequestException`，C 的 HTTP 服务返回格式错误
  的 JSON（`resp.json()` 抛 `JSONDecodeError`）现在也会原样往上抛，不再
  被当成"服务不可用"吞掉。真实验证过两条路径：① 模拟 `c_validate()`
  内部抛出真实业务异常（`RuntimeError`）——现在会正确地一路往上传，
  不会被吃掉；② 模拟模块真的导入失败（环境问题）——仍然正确降级到
  Mock，行为不变，没有破坏原有的合理降级场景

### 28. WebSocket 事件队列是单消费者，任务跑完之后重连/多开页面会永久卡住
- **在哪**：`backend/api/routes/websocket.py` 第22-26行 `await task.queue.get()`；
  `backend/api/task_manager.py` 第30行 `done: bool = False` 字段
- **实际情况**：`task.queue` 是一个普通 `asyncio.Queue`，没有广播/重放能力。
  ① 如果同一个 `task_id` 有两个客户端连接（浏览器网络抖动重连，或者开了两个
  标签页），事件会被两个连接分走，谁先 `get()` 到算谁的，两边都看不到完整的
  日志流；② 如果客户端是在流程**已经跑完之后**才连上 WebSocket（比如页面
  刷新晚了几秒），此时 `END_SENTINEL` 早就被前一个连接消费掉了，这个新连接
  的 `await task.queue.get()` 会**永远卡住**，既不会立刻关闭，也不会重放最终
  结果。`task.done` 这个字段本来看起来是为了处理这种情况设计的，但全仓库
  grep 确认它只在第80行被赋值一次，**从来没有任何地方读取它**——没有起到
  任何作用
- **状态**：✅ 已修复（07-04）。把"一个任务配一个共享 Queue"改成"一份完整
  事件历史（`task.history`） + 每个 WebSocket 连接各自独立的订阅 Queue
  （`subscribe()`/`unsubscribe()`）"：新连接先重放 `history` 补齐错过的部分，
  再继续从自己的 Queue 收后续实时事件；"任务是否已结束"不再依赖那个写了没人
  读的 `done` 字段（已删除），改成直接看 `history` 里出没出现过
  `END_SENTINEL`，天然跟事件流保持一致。真实验证过两个场景（用 FastAPI
  `TestClient` 走真实 `/api/submit` + `/ws/tasks/{id}`，只是把耗时的真实
  LLM 调用换成假的快速/慢速伪造流程，WebSocket 传输层本身是真的）：
  ① 任务完全跑完之后才连接——0.01 秒内收到完整重放并自动关闭，不再永久
  卡住；② 任务跑到一半时两个连接同时订阅——两边各自收到完全相同的 6 条
  完整事件流，不再被瓜分

### 29. `run()` 自己没有异常处理，失败路径不满足文档承诺的返回契约
- **在哪**：`backend/pipeline/run.py` 第104-134行
- **实际情况**：`graph.invoke()`/`graph.stream()` 和 `_zip_output()` 外面完全
  没有 `try/except`。CLAUDE.md 的架构原则明确要求"任何模块失败必须抛出明确
  异常"——如果 `decompose_node`/`validator_node` 真的按这条原则抛出异常，
  这个异常会直接从 `run()` 里裸奔出去，`run()` 承诺的返回值
  `{"deliverable":...,"test_report":{...}}`（CLAUDE.md 和 `run.py` 自己的
  文档字符串都是这么写的）**在失败路径上根本不会产生**。现在能撑住的原因
  只是因为 `backend/api/task_manager.py` 第74-78行凑巧用
  `try/except Exception` 包住了调用，把崩溃翻译成一个形状完全不同的
  `{"type":"error",...}` 事件——如果换一个直接调用 `run()` 的场景（脚本、
  未来的测试、CLI），拿到的就是一个没处理过的裸异常，不是干净的失败状态
- **另外一个相关问题**：就算流程完全没生成任何文件（比如某个节点提前非致命
  失败），`_zip_output()` 对着一个不存在的目录跑 `os.walk()` 不会报错，只会
  静默产出一个**内容为空但格式合法的 zip 文件**当"交付物"返回；顶层
  `{"type": "done", ...}` 事件跟真正成功时长得一模一样，前端只有深入
  `test_report.backend_generated`/`validation_passed` 字段才能看出"其实
  什么都没生成"
- **状态**：✅ 已修复（07-04）。给 `graph.invoke()`/`graph.stream()` 外面
  包了一层 `except Exception as e: raise RuntimeError(...) from e`——不是
  吞掉异常，是把裸的内部异常（可能是 LangGraph/Pydantic 深层报错，单看
  类型不知道是 `run()` 哪一步炸的）包装成一条说清楚"需求处理流程失败+
  是哪个需求"的清晰错误，`from e` 保留原始 traceback 方便排查。另外加了
  一道检查：`final_state` 里 `backend_code`/`frontend_code` 都是空的话，
  直接 `raise RuntimeError(...)` 拒绝打包，不再静默产出一个"格式合法但
  内容为空"的 zip 冒充交付物。真实验证过两个场景：① 模拟节点内部抛出
  `ValueError`——现在被包装成清楚的 `RuntimeError` 正确抛出（不是裸异常
  泄露）；② 模拟流程跑完但没生成任何代码——现在正确拒绝打包空 zip，抛出
  清楚的 `RuntimeError` 而不是返回一个看起来正常的空交付物。两种情况
  OpenTelemetry 的 span 里也正确记录了异常，没有被静默吃掉

### 30. C 的验证模块把"环境问题"和"代码真的写错了"混为一谈，会烧完所有重试
- **在哪**：`backend/agents/validator/server.py` 第73-87行
- **实际情况**：这里不是像 #27 那样静默造假（这处诚实地把异常转成
  `passed: False` 并把错误类型/信息写进 `logs`，值得肯定），但问题在于：
  如果失败原因是"这台机器没装 pywinauto"、"没有图形界面/显示器"这类
  **环境问题**，跟"代码真的有 bug"在 `should_retry` 眼里是完全一样的
  `validation_passed: False`——会触发跟真实代码缺陷一样的重试流程，
  5 轮重试全部烧完（每轮都是一次真实付费的 DeepSeek API 调用），最终结果
  里也没有任何字段区分"这轮失败是环境不行"还是"这轮失败是代码写错了"
- **状态**：未修复，优先级中等——不会造假成功，但会造成不必要的 Token 消耗

### 31. Windows 下 emoji/GBK 控制台崩溃只是环境变量绕过，代码本身没有修
- **在哪**：`backend/agents/validator/server.py`（第114行左右 `print("🚀 ...")`）
  和 `backend/agents/validator/_selftest.py`（贯穿全文件的 `✅`/`❌`/`⚠️`/🎉 打印）
- **实际情况**：`problem.md` 第13条已经记录过这个崩溃是靠外部设置
  `PYTHONIOENCODING=utf-8` 环境变量绕过的，"没改她代码"。全仓库 grep
  确认代码里没有任何 `PYTHONIOENCODING`/`sys.stdout.reconfigure(encoding=...)`/
  `chcp` 这类代码层面的修复。这意味着：任何人（队友、助教、之后的你自己）
  在一台新机器/新终端上，不记得手动设这个环境变量，直接跑
  `python -m backend.agents.validator.server` 或 `_selftest.py`，会**原样
  复现当初那次崩溃**——这是"绕过"，不是"修复"，修复应该是在代码里
  `sys.stdout.reconfigure(encoding="utf-8")` 这种一次性兜底，不依赖环境变量
- **状态**：✅ 已修复（07-04）。在 `server.py`/`_selftest.py` 顶部各加了
  `sys.stdout.reconfigure(encoding="utf-8")` + `sys.stderr` 同理，包一层
  `try/except (AttributeError, ValueError)` 兜底极少数 stdout 不支持
  reconfigure 的场景（比如被某些测试框架捕获）。不再依赖任何人记得手动设
  `PYTHONIOENCODING`。真实验证过：用 `io.TextIOWrapper(encoding="gbk")`
  模拟一个真实 Windows GBK 控制台——① 不加这个 reconfigure，直接打印
  emoji 确认会 `UnicodeEncodeError` 崩溃，复现了原始 bug；② 加上
  `reconfigure(encoding="utf-8")` 之后，同样的模拟 GBK 控制台，同样的
  emoji 打印，不再崩溃

### 32. `output_naming.py` 没有目录冲突处理，同名应用会静默覆盖上一次的产出物
- **在哪**：`backend/agents/experts/output_naming.py` 的 `resolve_output_dir()`
- **实际情况**：这个函数是纯函数，设计上就不感知文件系统状态（这是它的
  设计文档明确说的），所以两次语义相近的需求（比如同一句"做一个待办事项应用"
  跑两次，或者失败后重新跑一次 `run()` 对着同一个 `output_dir`）会解析出
  完全相同的路径，第二次会**静默覆盖**第一次生成的文件——没有警告、没有
  版本号、没有备份。空字符串/纯特殊字符的 app_name 边界情况倒是处理对了
  （会正确降级到 `_derive_app_name` 兜底），这条不是这个问题
- **状态**：未修复，两周内单次演示不会碰到，但多次迭代使用同一个输出目录时
  是真实的数据丢失风险

### 33. `POST /api/submit` 没有认证/限流，任何能连到端口的人都能触发付费 LLM 调用
- **在哪**：`backend/api/routes/tasks.py` 第14-20行
- **实际情况**：这个端口一旦被触发就是一整条真实调用 DeepSeek API 的付费
  流水线，且没有认证、没有限流、没有请求体大小限制。CORS 目前限制在
  `localhost:5173`（`main.py`），所以不能被任意网页跨站触发，只有能直接
  连到这台机器端口的人才能打——两周本地演示场景下风险可以接受，但如果
  以后要把这个服务暴露到局域网或公网，这里是第一个要补的口子
- **状态**：未修复，当前部署范围内优先级低

### 34. 整套编排/流水线代码没有任何自动化测试
- **在哪**：全仓库搜索确认，没有 `tests/` 目录、没有 `conftest.py`、没有任何
  pytest 配置
- **注意区分"工厂"和"工厂造出来的产品"，这条说的是前者**：`TestExpert` 生成
  pytest 代码、真实跑 `pytest --json-report` 这件事本身没有问题，是真实存在
  且真实验证过的（problem.md 第17条）——但那是"给**生成出来的应用**
  （比如 todo app）写测试"，测的是产品，不是测试这套"造应用的流水线"
  （`workflow.py`/`decompose.py`/`task_manager.py` 这些代码）本身对不对。
  打比方：工厂造车的时候会给每台出厂的车做质检（= TestExpert 干的事），
  但"造车的流水线本身有没有 bug"从来没人测过（= 这一条说的事）——这次两轮
  审查抓到的好几个 bug（重试次数算错、validator_stub 静默造假）都在流水线
  这一层，不在造出来的应用里
- **实际情况**：`backend/agents/experts/test_expert.py` 是"生成别人的测试的
  Agent"，不是测试 B 自己代码的测试；`_selftest.py` 是需要真实 Windows 桌面
  环境的手动脚本，没有 `assert` 结构，pytest 也收集不到它。也就是说，
  `workflow.py`、`task_manager.py`、`decompose.py`、`output_naming.py`、
  任何一条 API 路由——**没有一行是被自动化测试保护着的**。这次两轮审查
  发现的好几个 bug（重试次数差一次、重试路由只认后端、这次的 validator_stub
  静默吞异常），本质上都是"没有回归测试，写错了也没人告诉你"的同一个根因——
  每一条 `problem.md` 里"真实验证过"的记录，指的都是手动跑一次脚本看输出，
  不是可重复执行的测试用例
- **状态**：未修复，两周演示项目里加一套完整测试可能来不及，但这是"为什么
  这么多小 bug 能一直不被发现"的系统性原因，值得在复盘/答辩时明确说清楚

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
