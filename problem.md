# 已知问题清单

> 记录当前实现和文档承诺之间的落差，不是待办事项列表，是"诚实记账"——
> 方便后续决定哪些要补、哪些接受现状、哪些要改文档降低承诺。
> 已修复的问题不再堆在这个文件里，统一挪到 [problem_passed.md](problem_passed.md) 存档，
> 这个文件只留还没解决/暂不处理的问题，读起来更快找到真正待办的东西。
> 更新日期：2026-07-08（新增 #54：真实用 pywinauto 手动点击刚生成的记账应用
> "添加"按钮，实测必现 `NameError: name 'db' is not defined`——FrontendExpert
> 给同目录必然存在的 db 模块写了没人要求的 try/except 兜底导入、起了别名
> `_db`，业务逻辑却用了未绑定的裸名字 `db`；这个 bug 之前被 ttk/tk 按钮检测
> 不到的问题挡住从未暴露，那个按钮问题修复后才第一次真实点击到"添加"、
> 撞见此 bug，用户确认这个报错在实际使用中经常出现，不是这次生成的偶然
> 个例。新增 #55：`ui_interact` 的 `row_count_increases` 检测经常判定失败，
> 疑似是 #54（或同类前端运行时错误）的下游症状而非检测机制本身的独立问题，
> 待 #54 修复后重新观察再确认。当天另完成三处修复（ttk 按钮检测、Validator
> 启动子进程未隔离 cwd 导致所有生成应用共享根目录 app.db、BackendExpert
> 可能选用不稳定的全局连接缓存模式），均已通过真实调用/pywinauto 实测验证，
> 记录见 problem_passed.md）
>
> 2026-07-07（#21 拆分：其中"重试只会回头改 BackendExpert"的部分
> 已修复挪到 problem_passed.md，只剩"迭代次数比文档少一次"这半留在这里，
> 编号不变；#42（验收标准拍平后丢失任务类型归属，是修 #21 的结构性前置
> 阻塞项）已修复挪走；新增 #51：修完 #21 后，`FrontendExpert`/`BackendExpert`
> 生成失败时直接 `raise` 会绕过重试预算把整条流程崩溃退出，是真实测试中
> 撞上并已修复的新问题，记录见 problem_passed.md）
>
> 2026-07-06 历史记录：把 22 条已修复记录挪到 problem_passed.md；
> 新增第三轮代码审查 #39-45，其中 5 条已修复挪走，#41/#42 未修复留在这里；
> 新增 #46：MCP 工具从未被 Agent 自主调用过，主链路完全绕开 MCP 协议直接调
> 普通函数；#47（BackendExpert 重试拿不到上一轮失败原因）/#48/#49/#50
> （Commander JSON 兜底路径被误删/ruff 裸命令调用/桌面截图被遮挡窗口覆盖）
> 冒烟测试中真实复现并已修复；复核 #14/#19/#22/#26 时发现 #22 已被早前改动
> 连带修复、#19 描述过时（5项里3项已被删除），#19/#26 委派 Codex 处理并验收
> 通过，#22 直接确认挪走；#14 用户推翻了之前"不修"的决定，ollama_client.py
> 改名 llm_client.py + 删掉 Ollama 分支，全部记录在 problem_passed.md）

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

### 7. 完全没有记忆持久化
- **在哪**：CLAUDE.md 设计了 mem0 + ChromaDB + LangGraph MemorySaver 三层记忆
- **实际情况**：全项目搜索 `checkpointer`/`MemorySaver`/`chromadb`/`mem0`，零命中。
  `graph.compile()` 没传 `checkpointer`，`run()` 每次调用完全无状态，
  上一次生成过什么、失败过什么，下一次调用完全不知道
- **状态**：CLAUDE.md 里标为"选做"，Week 2 才计划做，不算失职，但目前是彻底的空白，
  不是"简化版"，是"完全没有"

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

---

## 代码审查第二轮（2026-07-04）：API 并发层 / 完整状态机 / 桌面自动化 / 异常吞噬 / 测试覆盖

> 第一轮审查完 `tools/`、`mcp_tools/`、`commander/`、`experts/`、`validator` 的
> checkers/run/schemas 之后，这一轮补上还没细看的部分：`backend/api/` 全部、
> `workflow.py`/`pipeline/run.py` 完整状态机、`validator/server.py`/`_selftest.py`、
> `output_naming.py` 边界情况、全仓库"静默吞异常"模式排查、测试覆盖率现状。
> 下面每一条都经过本人二次核对源码确认，不是子任务报告直接照抄。
>
> 这一轮里 #27（validator_stub 静默造假）/#28（WebSocket 单消费者卡死）/
> #29（run() 异常处理与空交付物）/#31（GBK 控制台崩溃）已修复，记录挪去了
> problem_passed.md，下面只留没修的。

### 21. `count_iteration` 计数时机导致实际重试轮数比文档少一次
- **在哪**：`backend/graph/workflow.py` 的 `count_iteration`/`should_retry`
- **实际情况**：`count_iteration` 在**第一次**验证（不是重试，是第一次跑）
  之后就已经 `+1`，`should_retry` 在 `iteration_count >= 5` 时停止——实际
  效果是"第一次尝试 + 4 次重试"，不是文档/`project_state.py` 字段注释里
  写的"最多重试 5 次"。少了一次真实的修复机会，不报错，只是安静地比设计值
  少跑一轮
- **状态**：未修复。（原 #21 还记录了"重试只会回头改 BackendExpert，
  FrontendExpert 永远不会被重新触发"这个问题，07-07 已经按 `failed_tests`
  的 `task_type` 修复，记录挪去了 problem_passed.md——这里只剩这一条还没处理）

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

### 30. C 的验证模块把"环境问题"和"代码真的写错了"混为一谈，会烧完所有重试
- **在哪**：`backend/agents/validator/server.py` 第73-87行
- **实际情况**：这里不是像 problem_passed.md #27 那样静默造假（这处诚实地把
  异常转成 `passed: False` 并把错误类型/信息写进 `logs`，值得肯定），但问题在于：
  如果失败原因是"这台机器没装 pywinauto"、"没有图形界面/显示器"这类
  **环境问题**，跟"代码真的有 bug"在 `should_retry` 眼里是完全一样的
  `validation_passed: False`——会触发跟真实代码缺陷一样的重试流程，
  5 轮重试全部烧完（每轮都是一次真实付费的 DeepSeek API 调用），最终结果
  里也没有任何字段区分"这轮失败是环境不行"还是"这轮失败是代码写错了"
- **状态**：未修复，优先级中等——不会造假成功，但会造成不必要的 Token 消耗

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
  且真实验证过的（problem_passed.md 第17条）——但那是"给**生成出来的应用**
  （比如 todo app）写测试"，测的是产品，不是测试这套"造应用的流水线"
  （`workflow.py`/`decompose.py`/`task_manager.py` 这些代码）本身对不对。
  打比方：工厂造车的时候会给每台出厂的车做质检（= TestExpert 干的事），
  但"造车的流水线本身有没有 bug"从来没人测过（= 这一条说的事）——这次几轮
  审查抓到的好几个 bug（重试次数算错、validator_stub 静默造假）都在流水线
  这一层，不在造出来的应用里
- **实际情况**：`backend/agents/experts/test_expert.py` 是"生成别人的测试的
  Agent"，不是测试 B 自己代码的测试；`_selftest.py` 是需要真实 Windows 桌面
  环境的手动脚本，没有 `assert` 结构，pytest 也收集不到它。也就是说，
  `workflow.py`、`task_manager.py`、`decompose.py`、`output_naming.py`、
  任何一条 API 路由——**没有一行是被自动化测试保护着的**。这几轮审查
  发现的好几个 bug（重试次数差一次、重试路由只认后端、validator_stub
  静默吞异常），本质上都是"没有回归测试，写错了也没人告诉你"的同一个根因——
  每一条 `problem.md`/`problem_passed.md` 里"真实验证过"的记录，指的都是
  手动跑一次脚本/一次完整流程看输出，不是可重复执行的测试用例
- **状态**：未修复，两周演示项目里加一套完整测试可能来不及，但这是"为什么
  这么多小 bug 能一直不被发现"的系统性原因，值得在复盘/答辩时明确说清楚

### 35. 三个专家 Agent 都只读同类型任务里的第一条，Commander 若给出多条同类型任务会被静默丢弃
- **在哪**：`backend/agents/experts/test_expert.py` 第65-66行
  `test_tasks[0].description`、`backend/agents/experts/backend_expert.py` 第64行
  `backend_tasks[0].description`、`backend/agents/experts/frontend_expert.py`
  第63行 `frontend_tasks[0].description`——三处写法完全一致
- **实际情况**：`SubTask.type`（`backend/agents/commander/schemas.py` 第43行）
  只是一个 `Literal["frontend", "backend", "test", "ui_validate"]`，Pydantic
  层面完全没有约束"每种 type 只能出现一次"。三个专家节点都用
  `[t for t in decomp.tasks if t.type == "xxx"][0]` 这种写法只取列表第一条，
  如果 Commander 某次输出了 2 条 `type: "test"`（或 2 条 backend/frontend）的
  任务——比如把"测试增删"和"测试边界情况"拆成两条子任务——第二条的
  `description`（以及它对应的 `acceptance_criteria`）会被**静默丢弃**，不报错、
  不警告，专家 Agent 只会看到并实现第一条任务描述的内容。等到 Validator
  按 `acceptance_criteria` 逐条核对时，被丢弃那条任务的验收标准永远核对不到
  对应实现，要么被判失败触发无意义的重试，要么验收标准本身写得宽松侥幸
  蒙混过关
- **为什么现在没暴露**：`commander_prompt.py` 第41行"最多拆成4个任务"+
  第59-90行的示例固定给 4 个任务、每种 type 恰好一条，这是**约定俗成的隐性
  假设**，没有一条规则明确写"每种 type 只能有一条"，纯粹靠 prompt 的示例
  强引导 LLM 这么做，真正触发概率低但没有任何机制兜底
- **状态**：未修复。修复方向不难——三处 `[0]` 改成遍历 `test_tasks`/
  `backend_tasks`/`frontend_tasks`，把多条 `description` 拼接后再传给 LLM
  prompt；但目前只是记录问题，尚未改动代码

### 36. 后端/前端/测试三个专家 Agent 的产出模型是"恰好一个文件"，没有多文件/多模块扩展路径
- **在哪**：`backend/agents/experts/backend_expert.py` 第90行
  `write_file(f"{app_output_dir}/db.py", code)`、
  `backend/agents/experts/frontend_expert.py` 第89行
  `write_file(f"{app_output_dir}/app.py", code)`、
  `backend/agents/experts/test_expert.py` 第95行
  `write_file(f"{state['app_output_dir']}/test_app.py", test_code)`；三处的
  `_extract_code()` 逻辑也完全一致，只从 LLM 回复里找**一个**
  ```` ```python ... ``` ```` 代码块
- **实际情况**：`BackendExpert` 不管应用的业务域是什么（todo/记账本/笔记...），
  永远把生成的后端代码写到同一个固定文件名 `db.py`；`FrontendExpert` 永远写
  `app.py`；`TestExpert` 永远写 `test_app.py`。`TestExpert` 的 system prompt
  里"测试文件会和 db.py 放在同一个目录下运行"（第76行）这句话之所以能这么
  写死，正是因为 `BackendExpert` 的输出路径本身就是写死的——两边是自洽的，
  不是互相脱节的两个假设。但这意味着整套"软件工厂"的产出模型从设计上就是
  **后端 = 恰好 1 个文件，前端 = 恰好 1 个文件，测试 = 恰好 1 个文件**，
  没有 routes/models/services 这种分层，LLM 被要求把整个后端逻辑一次性塞进
  单个文件的单次输出里
- **为什么现在没暴露**：CLAUDE.md 的演示场景本身设计的就是"待办事项"这类
  单文件 CRUD demo（`todo_db.py`/`todo_app.py`），需求足够简单，单文件足够
  覆盖。一旦需求复杂到需要多个数据模型、需要接口分组，这套架构没有扩展
  路径——不是"多文件支持暂时没做"，而是 prompt 设计和落盘逻辑的前提从根上
  就是单文件，复杂需求下大概率会先撞上单次 LLM 输出长度上限和代码质量的
  瓶颈，而不是被架构限制主动拒绝
- **状态**：未修复，两周演示范围内（单一 demo 级应用）不构成问题，但这是
  "软件工厂"这个定位与"单文件生成器"实际能力之间的落差，值得在复盘/答辩时
  明确说清楚，不宜暗示系统能生成结构完整的多模块后端

### 37. `plan`/`review`/`ship` 三个 SKILL.md 已补齐，但只是文档，还没接进代码
- **在哪**：`backend/skills/plan/SKILL.md`、`backend/skills/review/SKILL.md`、
  `backend/skills/ship/SKILL.md`（07-05 新增）
- **实际情况**：CLAUDE.md"目录结构"一节原本设计的是 6 个 Skill
  （`spec/plan/build/test/review/ship`），实际仓库长期只有 3 个
  （`spec`/`build`/`test`），`plan`/`review`/`ship` 三个文件夹此前压根不存在。
  这次补齐了这 3 个，内容分别对应 Commander 的任务分配步骤（`plan`）、
  Validator 的验收审计（`review`）、`pipeline/run.py` 的打包交付逻辑（`ship`），
  写法上跟已有的 `spec`/`build`/`test` 保持同样的 frontmatter + 执行规则/
  质量检查点结构。但跟 problem_passed.md 第6条修复的 `spec`/`build`/`test`
  不同，这三个**目前没有任何代码读取它们**——`loader.py` 的
  `load_skill_prompt()` 函数虽然对任意 skill 名通用，但没有任何地方调用
  `load_skill_prompt("plan")`/`load_skill_prompt("review")`/
  `load_skill_prompt("ship")`
- **为什么先只补文档不接代码**：`ship` 尤其特殊——它对应的不是某个 LLM
  Agent，而是 `pipeline/run.py` 里 `_zip_output()` 这段纯逻辑打包代码，
  "追加进 System Prompt"这个接入方式对它不适用，需要单独设计（比如当成
  代码审查 checklist 用，而不是塞进某个 LLM 调用）；`plan`同理更适合先确认
  要不要和 `spec` 合并进 Commander 同一次 LLM 调用，还是拆成两次调用，
  再决定怎么接
- **状态**：未修复（只完成了"补文档"这一半），是否要接入、怎么接入见
  "待决策事项"

---

## 代码审查第三轮（2026-07-05）：三路并行审查 backend/agents、backend/api+mcp+skills、frontend

> #39（Validator 逐轮结果没有实时推给前端）/#40（loader.py 异常类型不符）/
> #43（WebSocket 事件 Pydantic 模型是摆设）/#44（validator 包初始化的导入
> 副作用）/#45（前端 HealthStatus 类型不符）都已修复，记录挪去了
> problem_passed.md。#42 当时复核判定暂不处理，07-07 已修复（见 #21 的
> 前置阻塞项说明），记录也挪走了。下面 #41 复核后判定暂不处理，留在这里。

### 41. Commander 的 structured-output 空任务回退路径会让同一次请求被计费两次
- **在哪**：`backend/agents/commander/decompose.py:111-124`（`_try_structured_output`）
- **实际情况**：`.with_structured_output()` 返回的对象即使 schema 合法，只要
  `parsed.tasks` 为空，`_try_structured_output` 就直接 `return None`（不抛异常），
  `log_call(..., success=parsed is not None)` 已经按"失败"记了一次调用。
  `decompose()` 拿到 `None` 后紧接着跑 JSON-fallback 路径（171-197 行），
  又对同一个用户请求调用一次 DeepSeek 并 `log_call` 第二次
- **后果**：两次调用都是真实请求，不是重复 bug，但 Token 记账（problem_passed.md
  第12条）没有区分"结构化输出返回空任务"和"完全独立的第二次尝试"——每当命中
  这条路径，Token 面板里 `by_caller["commander"]` 的调用次数就会比实际发生的
  Commander 调用多算一次
- **复核结论**：不修复。重新看了一遍——两次 `log_call` 对应的是两次真实发生
  的 DeepSeek API 调用（各自消耗真实 token/花费），把它们都记下来是准确的，
  "多算一次"只是相对于"用户直觉上的一次 decompose() 调用"而言，不是记账
  逻辑本身有错。要区分"重试"和"独立尝试"需要在 `call_log` 表里加新字段
  （比如 `retry_of` 或 `attempt_kind`），这是记账 schema 的扩展，不是 bug 修复，
  且当前没有任何看板/查询在消费这种区分，先不做
- **状态**：未修复（评估后判定不是逻辑错误，是记账粒度的产品选择，不在"修
  bug/冗余/重复"范围内）

### 53. MCP 工具层是孤立文件，从没被启动过，专家节点全部绕开 MCP 协议直接 import 普通函数
- **在哪**：`backend/mcp_tools/mcp_server.py` 全文件；对比
  `backend/agents/experts/backend_expert.py:12,91`、
  `backend/agents/experts/frontend_expert.py:13,90`、
  `backend/agents/experts/test_expert.py:13-14,96,101,139`
- **实际情况**：
  1. `mcp_server.py` 用 `FastMCP` 把 `tool_write_file`/`tool_read_file`/
     `tool_run_command` 包装成标准 MCP 工具，文档字符串里给了一段"Agent 调用
     方式"的示例代码（`from langchain_mcp_adapters.tools import
     load_mcp_tools`）——但这只是写在注释里的示范代码，从没被真正执行过
  2. 全仓库搜索确认：没有任何地方调用 `load_mcp_tools`/`bind_tools`/
     `create_react_agent`/`ClientSession` 这类"让 LLM 拿到工具列表、自己决定
     调不调"的机制
  3. 更关键的是：真实流水线（`run.py`/`workflow.py`/`api/` 全搜过）里也没有
     任何地方启动 `mcp_server.py` 这个进程——它是个孤立文件，只能手动
     `python -m backend.mcp_tools.mcp_server` 单独跑起来，跟主链路完全没有交互
  4. 三个专家节点全部是 `from backend.tools.file_tools import write_file`/
     `from backend.tools.command_tools import run_command` 这种**直接 import
     普通 Python 函数**调用，完全绕开 MCP 协议这一层
- **后果**：CLAUDE.md"可直接采用的原题技术"一节把 MCP Protocol 标为"✅ 正确
  方向...modelcontextprotocol 已是行业标准"，"两周开发计划"Day 5 也写"Agent
  可调用 MCP 工具读写文件"——但实际运行时发生的是：LLM 只负责吐代码文本，
  之后是**写死的 Python 逻辑（不是 LLM）**决定何时调用 `write_file`/
  `run_command`、用什么参数，LLM 自己既看不到"这里有个工具"，也没有任何
  自主选择的空间。跟文档最开头"核心问题：动态编排是假的"是同一类问题——
  搭了一层看起来很标准的协议接口，但真实决策权完全不在 Agent 手里，"USB
  标准接口"（`mcp_server.py` 文档字符串原话）目前谁都没插
- **状态**：未修复（新发现，尚未讨论是否要真的把 MCP 接入 Agent 的工具调用
  决策链路，还是接受现状——把 `mcp_server.py` 定位成"独立可选的工具服务，
  演示/文档用，不是主链路依赖"，降低对外的承诺程度）

---

## 真实端到端点击测试（2026-07-08）：发现两个自动化检查全部漏检的问题

> 前三轮代码审查都是"读代码找问题"，这次不一样——真的启动了一次生成的
> "个人记账应用"，用 pywinauto 脚本模拟真实用户操作：填表单、聚焦窗口、
> 真实点击"添加"按钮，而不是只读源码猜测。发现的两个问题都是**所有现有
> 自动化检查（compile/ruff/pytest/LLM 静态审查）全部放行，只有真人点击
> 才能暴露**的类型，说明当前验证链路对"运行时才触发的错误"覆盖是空的。

### 54. FrontendExpert 写的防御性导入代码前后别名不一致，`db.create_transaction()` 调用的是从未定义过的 `db`，导致"添加"必然崩溃

- **在哪**：`output/account_book/app.py:6-8`（导入）与 `app.py:234`（调用），
  这是某一次真实生成的产物，问题根源在
  `backend/agents/experts/frontend_expert.py` 的 `FRONTEND_SYSTEM_PROMPT`
  没有约束这类写法
- **实际情况**：生成的代码开头是：
  ```python
  try:
      import db as _db
  except ImportError:
      # 内存数据库，模拟 db 模块（方便在没有真实数据库时运行）
      ...FakeDB 兜底...
  ```
  模块被起了别名 `_db`，但 `add_transaction()` 方法里实际调用的是
  `db.create_transaction(...)`——裸名字 `db` 在这份文件里从未被绑定过。
  这不是接口不匹配，是同一个文件内部前后不一致的低级错误，但后果是
  100% 必现：只要点"添加"就崩，不看具体输入值
- **真实复现**：写了一个 pywinauto 脚本，复用项目自己的
  `backend/agents/validator/run.py::_launch_app`/
  `backend/mcp_tools/desktop_control.py` 真实启动这次生成的 `app.py`，
  `window.set_focus()` 确保窗口在前台，清空并填入金额/类别/日期，真实
  `click_input()` 点击"添加"按钮，截图证实弹出错误对话框：
  `数据库错误 - 添加失败：name 'db' is not defined`。多次复测均 100% 复现
- **为什么四层自动化检查全部放行**：
  1. 编译检查只查语法，`NameError` 是运行时错误，编译阶段查不出来
  2. `ruff check` 用的配置没有启用能抓"引用未定义名字"的规则（如 F821），
     即使启用也可能因为 `except` 分支里有条件性赋值被误判为"可能已定义"
  3. pytest 测试只覆盖 TestExpert 生成的 `db.py`（数据层），从不测
     `app.py` 的 GUI 代码，这个 bug 完全在测试覆盖范围之外
  4. Validator 的 LLM 静态审查只是"读代码猜语义"，不会真的去追踪一个
     变量在这份文件里有没有被正确绑定，历史上多轮验收都判定这类界面
     代码"看起来没问题"
  5. `ui_interact` 真人点击验证本来是唯一能抓到这个问题的机制——但在
     `frontend-ui/SKILL.md` 的 ttk 按钮检测问题（problem_passed.md 相关
     条目）修复之前，点击环节一直卡在"根本找不到按钮"（`class_name="Button"`
     扫描到 0 个），从未真正点到过"添加"按钮，这个 bug 长期被前一个 bug
     挡住，直到今天按钮问题修复后才第一次真实点击到、暴露出来
- **根因**：`FRONTEND_SYSTEM_PROMPT` 和 `/build`、`/frontend-ui` 两个技能
  文件都没有限制"不要给同目录下必然存在的 sibling 模块写
  try/except ImportError 防御性兜底导入"——`db.py` 和 `app.py` 由同一条
  流水线在同一个输出目录里生成，不可能出现"导入失败"的场景，这段防御代码
  是 AI 训练语料里常见的"优雅降级"套路，没人要求却主动写了出来，而这个
  结构（导入时起别名、业务逻辑用原名）天然容易在两处之间打错字
- **用户反馈**：明确反馈这个报错"蛮经常出现"，即同类问题在多次生成中
  反复出现，不是这次生成的偶然个例
- **状态**：✅ 已修复（07-09）。`FRONTEND_SYSTEM_PROMPT` 加了一条规则，禁止
  对同目录下必然存在的 db 模块写 try/except 兜底导入，直接
  `from db import 具体函数名`，见 problem_passed.md

### 55.（已通过移除 ui_interact 解决）`row_count_increases` 检测经常判定失败

> 07-09 更新：这条讨论到最后没有继续修 `ui_interact` 本身——用户实际观察
> 到的问题比"某个 widget 类型识别不了"更根本：整套"LLM 读代码猜一份操作
> 计划、执行器纯按位置把计划套到界面控件上"的设计完全没有语义理解能力，
> 会出现填错位置、选错控件、甚至做无意义操作（没有新记录就直接查询）这类
> 表现。评估后判定这是个需要教会 AI"识别标签和输入框语义对应关系"的多日
> 工程问题，不是这次能收敛的，决定**整体移除 `ui_interact` 交互点击验证**，
> 保留纯截图 + LLM 静态审查（读代码 + 截图判断，不做真实点击模拟）。已删除
> `backend/agents/validator/run.py` 里的 `_ui_interaction_check`/
> `_execute_interaction_plan`/`_json_from_llm_response`/`_relative_rect`/
> `_region_changed` 和 `validate()` 里的调用点，以及
> `validator_prompt.py` 里的 `INTERACTION_PLAN_SYSTEM_PROMPT`/
> `build_interaction_plan_prompt`。`desktop_control.py` 的通用控件操作函数
> 未删除（不止服务于 ui_interact，保留）。
>
> 顺带发现并修复了真正的根因问题（不是最初以为的 BackendExpert 不遵守
> 接口规范，而是 TestExpert）：`backend_expert.py` 早就有
> `_assert_api_functions_exist()` 硬校验函数名，两轮生成 BackendExpert 都
> 没触发失败；反而是 `test_expert.py` 完全没有校验它生成的测试代码引用的
> `db.*` 函数名是否真的存在于 `backend_code` 里——尽管 prompt 里已经把完整
> `backend_code` 摆在它面前，它仍然连续多轮写死 `add_record`/`get_records`
> 这类跟实际代码（`add_transaction`/`get_transactions`）对不上的名字。已加
> `_assert_test_uses_real_functions()` 校验并补上跟另外两个专家一致的
> "捕获异常、返回失败信号、走正常重试"的安全网（`test_expert_node` 之前
> 出错是裸 `raise`，会直接崩掉整条流程，不会优雅重试）。

原始记录（供参考，问题本身已不再适用）：

- **在哪**：`backend/agents/validator/run.py::_execute_interaction_plan()`
  里 `widget_type == "treeview"` 分支，`success_condition == "row_count_increases"`
  的像素比对逻辑
- **实际情况**：用户反馈日志里"❌第 1 次执行失败：操作前后不满足
  row_count_increases"这条失败经常出现。这条检测的逻辑是：点击"添加"前后
  各截一次图，对比 treeview 区域像素差异，判断是否新增了一行
- **和 #54 的关系**：如果点击"添加"实际触发的是 #54 描述的 `NameError`
  崩溃（或其他类似的前端运行时错误），那么根本不会有新记录写入，treeview
  自然没有任何像素变化，`row_count_increases` 判定失败是**正确的**——
  检测机制如实反映了应用真的没添加成功，不是检测本身有 bug
- **待确认**：目前没有逐一比对每一次"row_count_increases 失败"背后是否都
  对应一次类似 #54 的运行时崩溃，还是也存在检测机制本身的假阴性（像素
  差异阈值、弹窗遮挡、时序问题等）。在 #54 的根因（防御性导入模式）修复
  之前，无法准确区分"这条检测本身不准"和"它如实反映了应用真的坏了"
- **状态**：未修复，需要先处理 #54，重新观察这条失败是否显著减少，再判断
  `row_count_increases` 检测本身是否还有独立问题需要修

---

## 待决策事项

- **要不要把动态调度真的做出来**：让 `workflow.py` 根据 `task_decomposition.tasks`
  和 `dependencies` 动态搭图，而不是写死固定流水线。工作量不小，两周工期内是否值得，
  还是接受现状、在文档里降低"动态编排"这个说法的承诺程度，说清楚现在是简化版
- ~~Skills 层要不要真的接上~~（07-05 部分完成）：`spec`/`build`/`test` 已通过
  `loader.py` 接入，采用"保留硬编码 Prompt + 追加 SKILL.md 正文"而不是"完全
  从 SKILL.md 读取替换硬编码"，理由见 problem_passed.md 第6条修复记录。剩下
  待决策的是 `plan`/`review`/`ship`（第37条）——`ship` 不对应 LLM Agent，`plan`
  要不要和 `spec` 合并成一次 Commander 调用，这两个还没定
- ~~记忆层和 API 层谁先做~~：API 层已完成，记忆层仍是 Week2 选做，暂不处理
- **`estimated_iterations` 要不要接进重试上限**：现在固定 5 轮硬顶。如果要让
  Commander 的估计值生效，得想清楚是"软目标+5轮硬顶不变"还是真的动态改上限——
  后者有被 AI 估计值带偏、失去安全网意义的风险，偏向前者但还没定
- ~~#52 截图/交互工具没接入判断链路，要不要修、修到哪一步~~（已选定并实现方案三，
  07-08 完成，详见 problem_passed.md #52）：没有走"让 FrontendExpert 产出结构化
  元素清单"这个原方案设想的路子，改成让 Validator 侧的 LLM 直接读真实源码生成交互
  计划、执行器按控件创建顺序（不是文字/清单）定位——避免了给 FrontendExpert 的
  Prompt 再加一层"必须遵守清单命名规范"的约束。方案一（措辞澄清）和方案二
  （截图先跑+多模态核对）仍未做，跟方案三不冲突，如果想进一步加固判断质量可以
  再评估要不要叠加
