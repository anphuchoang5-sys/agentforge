# 已修复问题存档

> 从 [problem.md](problem.md) 挪过来的"已修复"记录，按问题编号顺序排列，方便回溯
> 每条当初是什么问题、怎么查出来的、怎么修的、怎么验证的。编号延续 `problem.md`
> 的原始编号，不重新排序——如果某个编号在这里找不到，说明它还没修，去
> `problem.md` 看。
>
> 挪动日期：2026-07-05。挪动本身不改动任何一条的内容，只是搬家，问题描述、
> 修复过程、验证记录全部原样保留。

---

### 2. `SubTask.acceptance_criteria` 生成了但从未被使用
- **状态**：✅ 已修复（07-03 晚间）。`workflow.py::validator_node()` 从
  `task_decomposition.tasks[].acceptance_criteria` 拍平取出清单，传给
  `validator_stub.py::validate(criteria=...)` 再转发给 C 的 `llm_check()`。
  真实测试过：LLM 逐条核对代码、引用具体行号，还真的判过一条"界面美观易用"
  没完全达标（`passed: False`），会触发重试闭环——不是摆设了

### 6. `skills/` 下三个 SKILL.md 完全没被运行时加载
- **在哪**：`backend/skills/{build,test,spec}/SKILL.md`，对齐 CLAUDE.md
  "Skills集成：调用对应Skill保证代码质量"这条职责
- **实际情况**：全项目搜索，除了 `output_naming.py` 里一句注释提了一下文件名，
  没有任何代码在运行时读取/加载这些文件。各专家 Agent 的 System Prompt
  都是硬编码在对应 `.py` 文件里的字符串，跟 SKILL.md 毫无关联
- **状态**：✅ 已修复（07-05）。新增 `backend/skills/loader.py`，提供
  `load_skill_prompt(skill_name)`：读取指定 Skill 的 `SKILL.md`，去掉 YAML
  frontmatter 后返回正文 Markdown（文件不存在时让 `FileNotFoundError` 原样
  抛出，不静默兜底成空字符串）。采用"叠加"而不是"整段替换"的接入方式——
  保留三个专家 Agent 现有的硬编码 `XXX_SYSTEM_PROMPT`（这部分已经调好、
  含具体领域细节，比如"数据库文件名固定为 app.db"），把 SKILL.md 正文追加
  在后面：`backend_expert.py`/`frontend_expert.py` 追加 `build` Skill，
  `test_expert.py` 追加 `test` Skill，Commander 侧在 `decompose.py` 里追加
  `spec` Skill（两处组装 prompt 的地方——`.with_structured_output()` 路径和
  JSON 解析兜底路径——都统一加了，不是只改一处）。`decompose.py` 原本就有
  "独立运行时 `backend` 包可能不在 `sys.path` 上"的兼容处理（`console_encoding`
  那段），这次 Skill 加载沿用同样的 `try/except ImportError` 降级模式，
  失败时退化成空字符串，不影响 Commander 原有功能。真实验证过：导入四个
  模块后检查 `BACKEND_SYSTEM_PROMPT`/`FRONTEND_SYSTEM_PROMPT`/
  `TEST_SYSTEM_PROMPT` 里确实包含对应 SKILL.md 的标题文字，`decompose.py`
  的 `_SPEC_SKILL` 变量确认加载到 503 字符的 spec 正文，且 frontmatter
  （`name: build` 这类字段）没有泄漏进最终 prompt。仍需说明的是：这只是
  "把 SKILL.md 正文塞进 prompt"这一种最简单的接入方式，不是 CLAUDE.md
  模块4 里设计的 L1/L2/L3 三层渐进式加载（没有"先看 description 做匹配"的
  发现层，也没有"脚本/引用文件按需加载"的穿透层），`plan`/`review`/`ship`
  三个 Skill 也还没接入代码（见 problem.md 第37条）

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

### 16. C 读取代码做 LLM 核对时有 8000 字符截断，长文件的测试标准验证不了
- **状态**：✅ 已修复（07-03 深夜）。C 的 `run.py::validate()` 加了可选参数
  `code_content`，`workflow.py::validator_node` 把 `state` 里已经完整存在、
  从没被截断过的 `backend_code`/`frontend_code`/`test_code` 拼好直接传过去，
  不用 C 再重新读硬盘+截断。真实验证过：17102 字符完整传递，LLM 能同时看到
  db.py 和 test_app.py 的完整内容，不再出现"文件被截断"

### 17. TestExpert 真实跑过的 pytest 结果，从未被传到 C 的验证流程里
- **状态**：✅ 已修复（07-03 深夜）。三处一起改：① `test_expert.py` 的 pytest 命令加
  `--json-report --json-report-file=pytest_report.json`，路径存进新增的
  `state["pytest_report_path"]`；② `validator_stub.py`/`workflow.py::validator_node`
  转发这个路径；③ C 的 `checkers.py::pytest_check()` 从桩函数改成真的解析 JSON 报告，
  提取失败用例的具体断言信息。真实验证过：正确读出"27个测试，23通过，4失败"，
  还抓到一个真实 bug（自增 ID 计数器没有在测试间重置）

### 27. `validator_stub.py` 静默吞掉 C 的真实验证异常，兜底成一个能编造"通过"的假 Mock（发现时本次审查最严重的一条）
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
  try/except 里，业务异常会原样往上抛，一路传到 `run()`（第29条已经记录
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

### 38. Skill 正文和硬编码 Prompt 拼在一起后，三处内容真实打架
- **在哪**：`backend/skills/spec/SKILL.md`、`backend/skills/build/SKILL.md`、
  `backend/skills/test/SKILL.md`——第6条把这三个 Skill 接入运行时之后，
  实际把最终拼出来的完整 prompt 打印出来检查才发现的
- **实际情况**：三处具体冲突
  1. **Commander**：`commander_prompt.py` 要求输出完整的
     `{app_name, api_spec, tasks, estimated_iterations}` JSON，但 `spec/SKILL.md`
     紧跟在后面又给了一份"## 输出示例"，只有 `{"functions": {...}}`——连
     `api_spec` 这层 key 都没有。同一个 prompt 里前后出现两份不兼容的
     "该输出什么格式"，`.with_structured_output()` 主路径受 API 原生 schema
     约束影响较小，但结构化输出失败后走的纯文本兜底路径
     （`_parse_json_fallback` + `TaskDecomposition.model_validate()`）完全暴露
     在这个风险下——模型学了 Skill 里那份精简示例，输出可能只有
     `functions` 一层，`model_validate()` 因为缺 `tasks`（必填字段）直接校验
     失败
  2. **BackendExpert/FrontendExpert**：硬编码 prompt 说"只用标准库，不引入
     额外依赖"，`build/SKILL.md` 规则3却说"不引入未在 requirements.txt 里的
     依赖"——`requirements.txt` 里有 `sqlalchemy`/`langgraph`/`fastapi` 这些
     工厂自己跑起来要用的包，字面上这条规则等于告诉模型"这些也能用"，跟前面
     "只用标准库"直接矛盾
  3. **TestExpert**：`test/SKILL.md` 规则2原文"测试必须真实运行：用
     run_command 跑 pytest，把结果写进 test_results"——这句话描述的是
     `test_expert_node` 这个 Python 函数自己在 LLM 回复之后做的事
     （[test_expert.py:100](backend/agents/experts/test_expert.py:100)），
     这次 `ChatOpenAI` 调用本身没有绑定任何工具，LLM 根本没有能力"调用
     run_command"。把这句话原样塞进 system prompt 等于让模型执行一件它做不到
     的事，有风险让它在回复里夹带"已运行测试"这类幻觉说明文字，反而违反
     同一个 prompt 里"只输出 Python 代码"的硬性要求
- **根因**：三份 SKILL.md 最初是作为独立静态文档写的，写的时候没有站在
  "这段文字最终会跟另一份已经很完整的 prompt 拼在同一次 LLM 调用里"这个
  角度考虑，各自的"输出示例"/"执行规则"都是按"这份文档自己独立成立"设计的
- **状态**：✅ 已修复（07-05）。`spec/SKILL.md` 把独立的顶层 JSON 示例改写成
  明确标注"只是 api_spec.functions 内部片段，不是完整输出"的片段示例；
  `build/SKILL.md` 规则3改成跟硬编码 prompt 一致的"只用标准库，不引入任何
  第三方依赖"，并注明 `requirements.txt` 是工厂自身依赖不是生成应用可用的
  依赖列表；`test/SKILL.md` 规则2和质量检查点都改写成"外部流程会跑 pytest，
  你要保证的是代码本身没有语法错误/import 不存在的模块"，不再要求 LLM
  自己执行动作。真实重新拼过三份最终 prompt 检查过，确认冲突文字已经不再
  同时出现
- **给未来接入更多 Skill 的教训**：优先选/写只规定代码风格、质量检查点这类
  "技术性建议"的 Skill，这类内容跟外层 prompt 天然不会冲突；一旦 Skill 里带有
  自己的"输出格式/输出示例"，一定要跟外层调用方已有的格式要求交叉检查，
  两边"两份格式说明"同时存在本身就是风险来源，不是"越详细越好"

### 39. Validator 逐轮结果没有实时推给前端，"契约对齐"只补了终态那一次
- **在哪**：`backend/api/event_translator.py` 的 `_on_validator`；`backend/pipeline/run.py:161-183`；
  `frontend/src/lib/agentClient.ts:162-184`
- **实际情况**：上次修复（"Validator结果契约对齐前端"）只是把 `passed`/`logs`/
  `screenshot`/`failed_tests`/`iteration` 这些字段补进了 `run.py` 里最终 `done`
  事件的 `result`。但每一轮验证真正发生时，`_on_validator` 只发 `log`/
  `node_status`/`progress` 三种事件，从不带这些字段——`agentClient.ts` 里
  `isValidatorPayload()` 在运行过程中永远匹配不上，只有整个任务结束后那一次
  `done` 事件能触发它。同时前端还写了 `case 'iteration': s.setIteration(...)`
  分支，但后端从没发送过 `type: "iteration"` 事件（`event_translator.py` 没有
  任何地方产出这个类型），是个死分支
- **后果**：一个要重试 2-3 轮才通过的需求，跑的过程中 UI 的"第 N 轮验证"计数、
  失败截图面板、失败测试面板全程不更新，直到任务彻底结束才一次性跳到最终值——
  用户看到的是"卡住了"而不是"正在重试"
- **连带的 UI 症状**：因为重试只回退 `backend_expert`（第21条），`frontend_expert`
  只跑一轮，DAG 图上 frontend 节点从第一轮起就一直保持绿色，其余节点在重试时
  反复变灰再变绿——用户会疑惑"前端节点为什么不动了"，这是第21条在前端侧的一个
  具体可见症状，之前没有单独记录过（这一条本身不算 bug，是第21条没修就会一直
  存在的表现，未处理）
- **状态**：✅ 已修复（07-05）。`_on_validator` 每轮结束时额外推一条无 `type`
  字段的扁平 Validator 结果（`{passed, logs, screenshot, failed_tests,
  iteration}`），`iteration` 用 `EventTranslator` 自己的 `_validator_runs`
  计数器（每次 `_on_validator` 触发 +1），不依赖 `workflow.py` 里有第21条相关
  疑点的 `state["iteration_count"]`。复用了前端已经写好的
  `isValidatorPayload()`/`applyValidatorResult()`——它只认"无 type 但有布尔
  passed"这个形状，不关心是中途推的还是 `done` 里带的，前端代码零改动。
  真实调用 `EventTranslator._on_validator()` 两次验证过 `iteration` 从 1 递增到
  2、`screenshot`/`failed_tests` 字段正确透传。之后又真实跑了一遍完整流程
  （真实 DeepSeek 调用 + 真实 pytest + 真实 pywinauto 截图），抓取原始
  WebSocket 报文确认这条扁平结果确实在 `done` 事件之前单独推送，浏览器里
  也确认"第 1 轮"+截图+"已通过"是在流程结束前就已经显示。`case 'iteration'`
  那个死分支未删除（保留无害，删除属于前端代码改动，超出当时"不动核心架构"
  的修复范围）

### 40. `backend/skills/loader.py:35` `_strip_frontmatter` 的实际失败模式和文档承诺不一致
- **在哪**：`backend/skills/loader.py:35`，`_strip_frontmatter` 里的
  `text.index("\n---", 3)`
- **实际情况**：`load_skill_prompt` 的文档字符串（对应第6条的修复说明）承诺
  "文件不存在时让 `FileNotFoundError` 原样抛出，不静默兜底"——但这只覆盖了
  "文件不存在"这一种情况。如果某个 SKILL.md 开头有 `---` 但没有闭合的 `---`
  （比如以后有人编辑时手滑删掉了），`text.index(...)` 会抛
  `ValueError: substring not found`，是文档完全没提到的另一种异常类型
- **触发条件**：当前 6 个 SKILL.md 文件的 frontmatter 都写得规范，暂未触发；
  下次有人编辑 SKILL.md 且未正确闭合 frontmatter 时，`decompose()`/三个
  expert node 会在还没调用 LLM 之前就直接抛出未预期的 `ValueError` 崩溃
- **状态**：✅ 已修复（07-05）。`_strip_frontmatter` 现在 `try/except` 住
  `str.index` 的 `ValueError`，重新抛出一个带具体文件路径、说明原因
  （"frontmatter 未闭合，找不到结尾的 ---"）的 `ValueError`，不再是原始的
  `substring not found`。仍然是 `ValueError`（不是文档说的 `FileNotFoundError`
  ——那个契约只对应"文件不存在"，两种失败原因保持各自独立、都明确，没有
  互相冒充）。真实构造过一个只有开头 `---` 没有闭合的字符串验证过会抛出新
  报错且信息正确；6 个真实 SKILL.md 文件通过 `load_skill_prompt` 正常加载
  未受影响

### 43. `backend/api/schemas.py` 里的 WebSocket 事件 Pydantic 模型全部是摆设
- **在哪**：`backend/api/schemas.py` 的 `LogEvent`/`NodeStatusEvent`/
  `ProgressEvent`/`DoneEvent`/`ErrorEvent`
- **实际情况**：全仓库搜索确认这几个模型零引用——`event_translator.py`/
  `task_manager.py` 全部手写裸 `dict` 直接 `websocket.send_json(event)`，
  完全绕开了这几个 Pydantic 模型。`NodeStatusEvent.id` 定义的
  `Literal["commander","backend","frontend","test","uivalidator","validator"]`
  约束因此形同虚设——`event_translator.py` 以后如果手滑打错某个节点 id，
  不会有任何校验拦下来，只会在前端 `updateNodeStatus` 里静默 no-op，问题
  发现不了
- **状态**：✅ 已修复（07-05）。在 `task_manager.py` 里 `push(event)` 的唯一
  出口加了 `_check_event_shape()`：按 `event["type"]` 查表用对应的
  Pydantic 模型 `model_validate()` 一遍，校验失败只打印带具体事件类型和原因
  的 `[WARN]`、不阻断推送——这是给未来手滑准备的安全网，不该让一个内部契约
  问题打断正在跑的用户任务。同时给 `_on_validator` 新推的无 `type` 扁平结果
  在 `schemas.py` 里补了对应的 `ValidatorResultEvent` 模型（之前这个形状在
  `schemas.py` 里根本没有定义），`_check_event_shape` 按"没有 type 字段但有
  布尔 passed"识别并校验这一种。真实跑过 `log`/`node_status`/`done`/`__end__`
  和新的扁平 Validator 结果五种事件过一遍 `_check_event_shape`，均未误报；
  之后真实跑一遍完整流程时也确认服务端日志没有出现任何意外 `[WARN]`

### 44. `backend/agents/validator/__init__.py:28` 的导入副作用和第27条的收窄捕获组合出新的失败边界
- **在哪**：`backend/agents/validator/__init__.py:28`（`from .server import app as fastapi_app`）
- **实际情况**：`server.py` 模块加载时会执行 `sys.stdout.reconfigure(encoding="utf-8")`
  （第31条）。第27条把 `validator_stub.py` 外层捕获从 `except Exception` 收窄成
  `except ImportError` 之后，`server.py` 初始化过程中抛出的任何非
  `ImportError`（比如某些环境下的 `OSError`/`RuntimeError`）现在会直接穿透
  `validator_node`，而不是像收窄前那样降级成 Mock
- **状态**：✅ 已修复（07-05），但用的是比"改捕获范围"更根本的方式：直接删掉
  `from .server import app as fastapi_app` 这行以及 `__all__` 里的
  `fastapi_app`。全仓库搜索确认这个别名零消费者——`python -m
  backend.agents.validator.server`/`uvicorn ...server:app` 两种启动方式都是
  直接导入 `server.py` 模块本身，不经过 `__init__.py` 这个别名。删掉之后
  `from backend.agents.validator import validate` 不会再连带把整个
  `server.py`（FastAPI app 构造 + `ensure_utf8_console()`）一起加载进来，
  副作用源头直接消失，不需要再纠结外层该收窄捕获到多宽。真实验证过
  `from backend.agents.validator import validate, health_check` 能正常导入

### 45. `frontend/src/lib/api.ts:56` `checkHealth()` 期待的字段后端根本不返回
- **在哪**：`frontend/src/lib/api.ts:56`（`HealthStatus.status: string`）对比
  `backend/agents/validator/server.py` 的 `/health` 端点
- **实际情况**：后端 `/health` 只返回 `{"pywinauto": bool, "ruff": bool,
  "py_compile": bool}`，没有 `status` 字段
- **影响**：`checkHealth` 目前全仓库零调用点，纯潜伏，`appStore.ts` 里已经
  预留了 `backendHealthy`/`healthDetails` 字段，等哪天真的接上健康检查 UI
  才会暴露这个类型不匹配
- **状态**：✅ 已修复（07-05）。`HealthStatus` 删掉了后端根本不返回的
  `status: string`，改成跟 `health_check()` 实际返回值一致的三个布尔字段。
  选择改前端类型而不是改后端加一个 `status` 字段，是因为 `/health` 是 C 的
  Validator 模块对外接口，`_selftest.py` 等 C 自己的代码可能依赖这三个字段
  的现状，改前端类型去匹配后端事实，比反过来改一个不归 B 所有的接口风险更小。
  `npx tsc --noEmit` 验证过改动后无新增类型错误

### 48. Commander 的 `.with_structured_output()` 对 DeepSeek 100% 必然失败，唯一真正能用的 JSON 兜底路径被当"备用方案"删掉了
- **在哪**：`backend/agents/commander/decompose.py`
- **实际情况**：Codex 在"violent 分支不允许 structured-output/JSON fallback
  之间自动降级"这条原则下，把 `_try_structured_output()` 失败后退化到 JSON
  兜底解析的整段逻辑删掉了，改成结构化输出一失败就直接 `raise`。冒烟测试时
  实测复现：DeepSeek 官方 API 文档确认 `response_format` 只支持
  `text`/`json_object` 两种，不支持 `.with_structured_output()` 依赖的
  `json_schema` 模式，调用会 100% 返回 `400 This response_format type is
  unavailable now`——不是偶发，是这个功能对 DeepSeek 从来没成功过一次。
  今天更早的测试日志里"结构化输出不可用，降级到JSON解析模式"这行 INFO 就是
  证据：每次都在打印，只是删掉兜底之前从来没被人注意到"这条路径其实每次
  都会走到"
- **状态**：✅ 已修复（07-06）。整个删掉 `_try_structured_output()`
  （它本来就是个必然失败、纯粹烧 Token 的尝试），把原来的 JSON 兜底解析
  直接扶正成 `decompose()` 唯一的实现路径（连试 3 次，逻辑跟被删之前一致）。
  顺手在 `ollama_client.py::generate_with_metrics()` 里给 DeepSeek 调用加了
  `response_format: {"type": "json_object"}`（DeepSeek 真正支持、官方文档
  推荐的模式），给 Ollama 调用加了等价的 `format: "json"`，让这条路径本身
  更可靠。真实调用 `decompose()` 验证过：第 1 次尝试直接成功，不需要用满
  3 次重试；随后真实跑通完整 UI 提交流程，Commander 不再崩溃
- **给这次教训**：这也是"委派 Codex 前要写清楚范围和验证要求"那条记忆的
  一次真实印证——"违背了 CLAUDE.md 里明文写的一条规则"和"删掉的东西其实是
  唯一真正能跑通的路径"两件事可以同时为真，字面执行文档规则之前，最好先
  确认一下"这条被判定为该删的路径，删掉之后还有没有别的东西能撑住"

### 49. `ruff_check` 用裸命令 `"ruff"` 调用，pip 装到用户目录时找不到，被误判成"没装"
- **在哪**：`backend/agents/validator/checkers.py::ruff_check`
- **实际情况**：`cmd = ["ruff", "check", ...]` 直接调裸命令名，依赖 `ruff.exe`
  所在目录在系统 PATH 里。用户实测复现：`pip install ruff` 确实把包装进了
  `AppData\Roaming\Python\Python313\site-packages`，可执行文件在同目录下的
  `Scripts\ruff.exe`，但这个 `Scripts` 目录默认不在 Windows 的 PATH 里——
  `subprocess.run(["ruff", ...])` 找不到命令抛 `FileNotFoundError`，代码里
  把这个异常直接解读成"ruff 未安装"，其实包装得好好的，只是调用方式不对。
  冒烟测试里这个问题被 Codex 早前的改动放大：以前"ruff 未安装"只是警告不
  阻断（problem.md 第30条描述的"环境问题不该占用重试预算"），现在被 Codex
  改成 `severity="error"` 直接判不通过——于是每一轮重试都在同一个跟代码质量
  毫无关系的地方失败，5 轮重试预算被无意义地烧光
- **状态**：✅ 已修复（07-06）。改成 `[sys.executable, "-m", "ruff", ...]`，
  跟项目里调 pytest 用 `python -m pytest` 是同一个思路，不依赖 PATH，只要
  当前 Python 环境装了 ruff 包就能跑。同时修了一个连带的潜在假通过：
  `python -m ruff` 在包没装时不会抛 `FileNotFoundError`（python.exe 本身
  肯定存在），而是非零退出码 + 空 stdout——原来的解析逻辑会把"空 stdout"
  误判成"0 个问题"直接放行，新增了一个"非零退出码且 stdout 为空"的显式
  分支拦住这种情况，不让"根本没跑起来"被静默当成"通过"。真实调用
  `ruff_check()` 验证过：现在能正确跑起来、正确解析结果、`passed=True`

### 50. 桌面截图会被其他遮挡窗口覆盖，截到完全不相关的内容
- **在哪**：`backend/mcp_tools/desktop_control.py::screenshot()`
- **实际情况**：用户实测复现：Validator 面板显示的"应用截图"内容是用户自己
  Claude Code 聊天界面的画面，根本不是生成出来的桌面应用。查证是 pywinauto
  的已知限制（[pywinauto issue #995](https://github.com/pywinauto/pywinauto/issues/995)
  确认）：`capture_as_image()` 不是从目标窗口的离屏绘制缓冲区取图，而是直接
  截取该窗口在屏幕上占的那块像素区域——如果这块屏幕区域被别的窗口（比如用户
  正在看的 Claude Code 窗口）遮挡，截到的就是盖在上面的内容，不是目标应用
  真正的画面
- **状态**：✅ 已修复（07-06）。在 `capture_as_image()` 之前加一行
  `window.set_focus()`，把目标窗口切到最前面再截图，避免被其他窗口遮挡。
  这不是 100% 杜绝所有极端情况（比如截图瞬间用户手动把别的窗口切到最前面），
  但覆盖了实际复现的这种"目标窗口一直在后台、被其他窗口常驻遮挡"的场景

### 47. 重试对 BackendExpert 是"瞎重试"，拿不到上一轮验证失败的具体原因
- **在哪**：`backend/agents/experts/backend_expert.py::backend_expert_node`
  的 prompt 组装部分
- **实际情况**：`prompt` 只由两样东西拼成——`task_desc`（Commander 给的原始
  任务描述，从第一轮到最后一轮完全不变）和 `api_spec_text`（接口规范，同样
  不变）。`ProjectState` 里其实已经有 `validation_logs`/`failed_tests` 这些
  字段，且这些字段在重试时（LangGraph 把上一轮的 state 原样带到下一轮）已经
  真实存在于 `state` 里——但 `backend_expert_node` 一行都没读，重试时发给
  DeepSeek 的 prompt 和第一次一模一样
- **实测复现**：用户真实跑了一个"记账本"需求，Validator 连续判定"月度统计
  的余额计算未实现"这条验收标准不通过，重试了至少 2 轮，每轮生成的代码都
  重复同一个缺陷——因为 BackendExpert 压根不知道自己上一轮错在哪，只是
  "又生成一遍，赌运气好点"，不是"看到报错后针对性修复"
- **跟 #21 的关系**：#21 说的是"重试有时候找错专家"（该修前端却只回退
  后端）；这一条是"就算侥幸找对了该修的专家，这个专家也不知道要修什么"——
  两个问题独立存在，#21 没修，这一条修了照样有价值（找对专家时至少能真的
  改对地方）
- **不需要接入记忆系统**：这纯粹是"当前这一次 run() 内部，同一个 `state`
  字典里已经有的数据没被读到"，跟 mem0/ChromaDB/LangGraph MemorySaver 那层
  跨会话记忆（problem.md 第7条）完全是两码事
- **状态**：✅ 已修复（07-06）。新增 `_build_retry_feedback(state)`：读
  `state.get("failed_tests")`，为空（第一次生成，Validator 还没跑过）就
  返回空字符串，prompt 跟原来完全一样；非空（重试轮次）就把每条失败原因
  （`[name] reason`）和上一轮生成的 `backend_code` 一起拼进 prompt 末尾，
  明确要求"基于失败原因修复对应问题，其余部分不要无意义大改"。
  `failed_tests` 是 Validator 对整份代码的失败清单，不只是后端的锅（可能有
  前端界面或测试用例相关的失败）——没有可靠办法过滤哪条属于哪个专家
  （problem.md 第42条：现有数据结构猜不出验收标准和任务类型的对应关系），
  所以选择全部给模型看，prompt 里明确提示"不属于后端职责的跳过，只处理你能
  改这份代码解决的部分"，交给模型自己判断，而不是用不可靠的字符串匹配瞎猜。
  真实验证：单元测试确认第一次生成时反馈内容为空、prompt 不受影响；重试
  场景下反馈内容正确包含失败原因和上一轮代码。更进一步，直接拿用户真实
  复现的那个 bug（`get_monthly_summary` 缺少余额计算）构造一模一样的重试
  输入喂给 `backend_expert_node`，重新生成的代码里正确加上了
  `balance = income - expense` 并写进返回值——不再是重复同一个缺陷

### 22. `validate()` 对空字符串路径的判断，跟"不许静默兜底"的架构原则冲突
- **在哪**：`backend/agents/validator/run.py`/`checkers.py` 里用
  `Path(app_path).exists()`/`.is_dir()` 判断路径是否存在，`workflow.py::validator_node`
  传入的是 `state.get("frontend_path", "")`
- **实际情况**：Python 的 `Path("").exists()` 和 `.is_dir()` 都返回 `True`
  （pathlib 把空字符串当成当前目录 `.`），所以如果 `frontend_path` 万一是空字符串，
  `read_app_code("")` 不会报错，而是会静默去**进程当前工作目录**扫最多 10 个
  `.py` 文件当成"要验证的代码"去读——这跟 CLAUDE.md 明确写的"任何模块失败必须
  抛出明确异常，禁止返回写死的假数据/静默兜底"这条架构原则直接冲突
- **状态**：✅ 已修复（07-06 确认，具体改动应是 07-06 当天更早的 Codex 改动的
  连带效果，不是这次单独动手改的）。`checkers.py::compile_check()`/
  `ruff_check()` 现在都在 `Path(app_path).exists()` 之前加了
  `if not app_path or not str(app_path).strip() or ...` 的显式空值检查
  （见 `_missing_path_failure()` 辅助函数），`read_app_code()` 自己也在最前面
  显式 `if not app_path or not str(app_path).strip(): raise ValueError(...)`。
  空字符串不再会被 pathlib 当成"当前目录存在"从而静默扫描 cwd，而是会在
  最外层就被挡下来、转换成明确的失败结果或异常。真实读代码确认了这几处
  检查都在，07-06 这次审查 #14/#19/#22/#26 时顺带核实到的，不是新修的

### 19. 确认零调用的死代码
- **在哪**：
  - `backend/mcp_tools/desktop_control.py` 的 `app_close()` / `app_connect()` / `launch_and_get_window()`
  - `backend/agents/commander/ollama_client.py` 的 `generate()`
  - `backend/agents/commander/decompose.py` 的 `decompose_with_metrics()`
  - `backend/agents/commander/call_log.py` 的 `get_stats()`
  - `backend/agents/validator/schemas.py` 的 `PASS_REPORT_TEMPLATE`
- **实际情况**：全部经过全仓库 grep 确认零调用方。07-06 复核时发现其中
  `generate()`/`decompose_with_metrics()`/`PASS_REPORT_TEMPLATE` 三项已经在
  更早的改动中被删掉了，问题描述已过时；实际还需要清理的只剩
  `app_close`/`app_connect`/`launch_and_get_window`/`get_stats` 四个
- **状态**：✅ 已修复（07-06）。委派 Codex 处理，写明边界（只删这几个函数
  本身+必须的连带 import 清理，不做其他重构）+ 范围 + 目标 + 测试要求。
  Codex 删除 `app_connect()`/`get_stats()`，但发现 `app_close()`/
  `launch_and_get_window()` 被 `backend/agents/validator/run.py` 的
  顶层 import 语句引用，而 `run.py` 不在授权编辑范围内——按指令正确停手，
  没有为了删除而删除，回来问要不要扩大范围。核实后发现 `run.py` 虽然
  import 了这两个名字，但从未真正调用过（`_launch_and_screenshot` 是直接
  用 pywinauto 自己写的逻辑，没用这两个辅助函数），确认后追加清理了
  `run.py` 的两处 import 语句（只留真正用到的 `screenshot`），再删掉
  `desktop_control.py` 里剩下的这两个函数，同步清理了 `mcp_tools/__init__.py`
  对应的 import/`__all__`/docstring 示例。真实验证：`py_compile` 全过；
  `from backend.mcp_tools import app_launch, ui_click, ui_input, ui_get_text,
  screenshot`、`from backend.agents.commander.call_log import log_call,
  get_recent_logs`、`from backend.agents.validator.run import validate,
  health_check, detect_app_type` 三处 import 都正常；全仓库 grep 确认这几个
  名字只在注释/docstring/print 字符串里出现，没有真实调用；最后真实调用
  `validate('./output/counter/app.py')` 端到端跑了一遍，截图功能正常产出
  16660 字符的真实图片（证明 `desktop_control.py` 的清理没有搞坏实际截图
  流程），不只是"能 import"这种浅层验证

### 26. `call_log.py` 的 `LOG_DB_PATH` 路径计算错误：日志库落在了仓库外面
- **在哪**：`backend/agents/commander/call_log.py` 第17行，
  `LOG_DB_PATH = Path(__file__).parents[4] / "data" / "call_logs.db"`
- **实际情况**：`call_log.py` 位于 `backend/agents/commander/call_log.py`，
  `parents[3]` 才是项目根目录，`parents[4]` 是再往上一级，实际解析成了
  仓库外的 `E:\data\call_logs.db`——不是理论风险，之前清理测试记账数据时
  已经实测验证过这个路径确实存在且在仓库外
- **状态**：✅ 已修复（07-06）。委派 Codex 处理，写明只改这一行、不动这个
  文件其他任何函数。Codex 改动本身正确（`git diff` 确认唯一改动就是
  `parents[4]` → `parents[3]`），但 Codex 自己环境缺 `python-dotenv`，
  它要求的两条验证命令没能真正跑起来。在能正常跑的环境里重新验收：
  `LOG_DB_PATH` 正确解析成 `E:\6.29agent\data\call_logs.db`（项目根目录下），
  `log_call()`/`get_recent_logs()` 写入+读出功能验证正常

### 14. `ollama_client.py` 文件名和内容具有误导性
- **在哪**：`backend/agents/commander/ollama_client.py`——早期纯 Ollama 架构的
  历史命名，DeepSeek 迁移后内部逻辑已经是 DeepSeek 优先，但文件名没跟着改，
  容易让人误以为还在用 Ollama
- **原本的状态**：曾经明确记录过"不修——本人评估过，改名涉及全项目 import
  路径，风险大于收益，暂缓"。用户 07-06 主动推翻了这个决定，条件是"确认现在
  代码只有接入 API 的逻辑"，并明确了新的项目策略："violent 分支就是不用
  本地模型"
- **状态**：✅ 已修复（07-06）。先探查确认：全仓库只有这一个文件真的有
  Ollama 相关运行时逻辑（`generate_with_metrics()`/`health_check()` 里各
  一个 HTTP 调用分支，两条路径本质都只是"发 HTTP 请求拿 JSON"，没有真的在
  本地加载/跑模型的复杂逻辑），其余 5 个引用它的文件只是 import 模块名或者
  提示文案里提了句"ollama serve"。原计划委派 Codex 处理，但 Codex 转发机制
  被 Claude Code 的自动模式安全分类器拦截（转发任务的写法本身被误判成"绕过
  监督"模式，不是内容问题），用户选择改为直接执行。最终改动：
  1. `git mv ollama_client.py llm_client.py`（保留 git 历史）
  2. 删除 `generate_with_metrics()`/`health_check()` 里的 Ollama 分支和
     `OLLAMA_BASE`/`OLLAMA_GENERATE` 常量，只保留 DeepSeek 路径；不是
     DeepSeek 模型或缺 `DEEPSEEK_API_KEY` 时明确 `raise RuntimeError`，
     不静默兜底
  3. 同步更新 5 处引用：`decompose.py`（2 处 import + 3 处提示文案，去掉
     "启动 ollama serve"这类过时提示）、`commander/__init__.py`（1 处
     import）、`checkers.py`（1 处 import + 4 处注释）、`validator_prompt.py`
     和 `llm_logging.py`（各 1 处注释）
  真实验证：全仓库 grep 确认无残留旧名字/旧常量；6 个文件 `py_compile`
  全过；真实调用 `health_check()` 返回 `True`；真实调用
  `decompose("做一个最简单的计数器应用")` 端到端跑通 DeepSeek API，拆出
  4 个任务；真实测试传入非 DeepSeek 模型名（`qwen2.5-coder:7b`）会正确抛出
  `RuntimeError`，不会静默路由到本地模型

### 18（重复编号，历史遗留——和 problem.md 里未修复的"18. 系统当前是'一次性执行'"不是同一条）。前端已对接真实 WebSocket，Mock 模式已切换为真实后端
- **说明**：这条在原文档里就用了和另一条不同问题重复的编号"18"，是历史遗留的
  编号冲突，不是这次搬家造成的，原样保留内容和编号，只加这行说明避免误认为
  和 problem.md 里那条"18. 系统当前是'一次性执行'，没有任何跨次记忆"是同一件事
- **状态**：已修复（07-04）
- **说明**：前端已从 Mock 模式切换到真实后端 WebSocket 连接，
  `POST /api/submit` 创建任务，`WS /ws/tasks/{task_id}` 接收实时推送，
  全流程（Commander → Backend → Frontend → Test → Validator）完整跑通。
  验证通过后自动截图，17 条验收标准全部通过。
- **联调结果**：验证通过（1 个 warning，无 error），测试 22/22 通过
