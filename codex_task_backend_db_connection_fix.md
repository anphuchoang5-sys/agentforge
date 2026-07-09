# Codex 任务简报：给 BackendExpert 的 System Prompt 加一条 sqlite3 连接生命周期硬规定

> 按 CLAUDE.md「委派 Codex 处理代码修改的规范」五项要求撰写。这是本任务唯一一次
> 派发简报——不会有后续"补充版"或"完整版"，Codex 应该按这一份完整执行。

## 1. 修改范围

**只改一个文件、一处字符串常量**：
[backend/agents/experts/backend_expert.py](backend/agents/experts/backend_expert.py)
里的 `BACKEND_SYSTEM_PROMPT` 字符串常量（当前第 20-28 行）。

**明确不许碰的文件/代码**（越界了就是这次任务失败，不是"顺手改进"）：
- 同一个文件里的 `_extract_code()`、`_build_retry_feedback()`、
  `_extract_frontend_imports()`（如果存在）、`backend_expert_node()` 等其他函数
  **一个字都不许改**，只改 `BACKEND_SYSTEM_PROMPT` 这一个字符串常量
- `backend/agents/experts/frontend_expert.py`、`test_expert.py`——这次只约束
  BackendExpert 一个人的行为，不碰其他专家
- `backend/skills/build/SKILL.md`——这个技能文件是 BackendExpert 和
  FrontendExpert **共用**的（两边的 System Prompt 都会 `load_skill_prompt("build")`
  拼接这份文件），这次要加的规则只对后端的 sqlite3 用法有意义，不该写进共用文件
  里去影响前端，所以规则要直接写进 `BACKEND_SYSTEM_PROMPT` 这个后端专属的字符串里
- `backend/graph/workflow.py`、任何 `backend/agents/validator/**`、`output/`
  目录下任何文件、任何其他 `SKILL.md`

## 2. 修改目标

**具体问题（真实复现，不是假设）**：刚跑的一次"个人记账应用"需求里，第 1 轮
重试时 BackendExpert 生成的 `db.py` 用了这种模式：

```python
_conn = None

def _get_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _new_connection()
        _init_table(_conn)
    else:
        try:
            _conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            _conn = _new_connection()
            _init_table(_conn)
    return _conn
```

模块级全局变量缓存一个长期存活的 `Connection` 对象，所有函数共用这一个连接，不是
每次调用各自开关。这本身是合法的工程选择，但当天配套的 `test_app.py`（同一轮由
TestExpert 生成）的隔离 fixture 没有正确处理这个"全局共享连接"细节，导致 pytest
报了 13/16 个测试失败，报错都是
`sqlite3.ProgrammingError: 无法对已关闭的数据库进行操作`——本质是测试之间用同一个
被意外关闭的连接对象互相踩踏。

第 2 轮 TestExpert 重新读了当轮实际的 `db.py`，正确写出了会显式重置
`db._conn = None` 并 `monkeypatch.setattr(db, "DB_NAME", ...)` 的 fixture，pytest
报告显示 9/9 全部通过——问题是自愈的，但整整浪费了一轮重试（约 3-5 分钟 + 一次
完整的三专家重新生成 + 真实 DeepSeek token 消耗）。

**根本原因**：Commander 生成的接口规范只锁定函数名/参数/返回类型（"接口优先设计"
架构原则），完全不规定函数内部**怎么管理数据库连接**——这是留给 BackendExpert
自由发挥的实现细节。但 BackendExpert 每次独立生成时，可能随机选择"每次调用各自
开关连接"（简单、无状态）或"模块级缓存单个长期连接"（省一点点性能，但引入了
"测试脚本必须知道内部有个全局连接需要手动重置"这个隐藏耦合）。TestExpert 是另一次
独立的 LLM 调用，只能通过读当轮实际生成的 `db.py` 源码去猜"这次到底选了哪种模式"，
猜对了没事，猜漏细节就导致这一轮测试全线失败——不是任何一方生成质量差，是两个
独立生成的文件之间存在一个规范里没锁死、只能靠"读代码猜实现细节"来同步的隐藏契约。

**目标**：直接约束 BackendExpert 只能使用"每次函数调用各自开关连接"这一种模式，
从源头上消除"模块级缓存连接"这个选项，这样 TestExpert 就永远不需要处理"读取/重置
全局连接缓存"这类隐藏契约——因为这个坑从设计上就不存在了。

## 3. 具体修改措施

把 `backend_expert.py` 里 `BACKEND_SYSTEM_PROMPT` 当前的完整原文（第 20-28 行）：

```python
BACKEND_SYSTEM_PROMPT = """你是一位专业的 Python 后端工程师。
你的任务是根据接口规范和任务描述，用 Python 实现后端数据层代码。

要求：
- 只用标准库，不引入额外依赖
- 数据存储方式根据任务描述判断：要求持久化保存就用 sqlite3（数据库文件名固定为 app.db）；
  要求内存存储/重启后丢失就不要用数据库，用模块级变量（list/dict）保存
- 严格按照给定的函数名和参数实现，不要改名
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 代码要能直接运行，不留 TODO
""" + "\n\n" + load_skill_prompt("build")
```

替换成（只在"要求"列表里插入一条新规则，其余逐字不变）：

```python
BACKEND_SYSTEM_PROMPT = """你是一位专业的 Python 后端工程师。
你的任务是根据接口规范和任务描述，用 Python 实现后端数据层代码。

要求：
- 只用标准库，不引入额外依赖
- 数据存储方式根据任务描述判断：要求持久化保存就用 sqlite3（数据库文件名固定为 app.db）；
  要求内存存储/重启后丢失就不要用数据库，用模块级变量（list/dict）保存
- 使用 sqlite3 时，每个函数内部各自独立开关连接（用 `with sqlite3.connect(DB_NAME) as conn:`
  或 try/finally 手动 `conn.close()`），当次操作完成后立刻关闭；不要在模块级用全局变量
  缓存/复用同一个 Connection 对象跨函数调用共享（不要写类似 `_conn = None` +
  `_get_connection()` 判断是否已关闭再重连的全局连接池模式）。原因：per-call 开关连接
  性能开销可以忽略，但能保证测试代码只需要 monkeypatch 数据库文件名/路径就能正确隔离，
  不需要额外知道并处理"内部缓存了一个共享连接对象，必须手动重置"这个隐藏实现细节
- 严格按照给定的函数名和参数实现，不要改名
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 代码要能直接运行，不留 TODO
""" + "\n\n" + load_skill_prompt("build")
```

除了这一条新增规则，`BACKEND_SYSTEM_PROMPT` 其余文字、文件里的其他函数都不许动。

## 4. Codex 自验证方法（改完必须自己做，不做不算交付）

1. 改完后重新读一遍 `backend_expert.py` 完整文件，确认只有 `BACKEND_SYSTEM_PROMPT`
   这个字符串常量发生变化，文件里其他函数（`_extract_code`、
   `_build_retry_feedback`、`backend_expert_node` 等）逐字未动。
2. 在项目根目录用 `.venv\Scripts\python.exe` 实际执行：
   ```
   python -c "from backend.agents.experts.backend_expert import BACKEND_SYSTEM_PROMPT; print(BACKEND_SYSTEM_PROMPT)"
   ```
   确认能正常导入、没有语法错误或异常，且打印出的内容里包含新增的这条连接管理规则，
   把真实终端输出贴出来。
3. 跑 `git diff --stat` 确认改动范围只有
   `backend/agents/experts/backend_expert.py` 这一个文件，贴出真实输出。
4. **不需要**（也不应该）重新触发一次完整的 DeepSeek 生成 + Validator 全链路跑
   一遍——那需要真实 API Key、跑 5-10 分钟、消耗真实 token 额度，这个决定应该留给
   人类。Codex 只需要验证"文件改对了、能被正常导入、没有越界改动其它文件"。

## 5. 验收标准（人类复核时要确认这些）

用 `Read` 工具直接读取 `backend/agents/experts/backend_expert.py` 改动后的**当前**
完整内容（不要只看 diff），确认：

- [ ] `BACKEND_SYSTEM_PROMPT` 里新增了一条明确要求"每个函数内部各自开关 sqlite3
      连接、不要用模块级全局变量缓存/复用 Connection 对象"的规则，并且写清楚了原因
      （per-call 开关性能开销可忽略、测试只需 monkeypatch 文件名不需处理隐藏连接
      缓存细节）
- [ ] `BACKEND_SYSTEM_PROMPT` 里原有的其余规则（只用标准库、数据存储方式判断、
      严格按函数名参数实现、代码块格式、不留 TODO）逐字未变
- [ ] 文件里其他函数（`_extract_code`、`_build_retry_feedback`、
      `backend_expert_node` 等）逐字未变
- [ ] Codex 贴出的 `python -c "from ... import BACKEND_SYSTEM_PROMPT; print(...)"`
      真实调用结果里，能看到新规则的完整文字（不是异常堆栈）
- [ ] `git diff --stat` 显示改动只涉及 `backend/agents/experts/backend_expert.py`
      这一个文件，没有出现 `frontend_expert.py`、`test_expert.py`、
      `backend/skills/build/SKILL.md`、`workflow.py`、`backend/agents/validator/**`、
      `output/` 目录下任何文件的改动

验收通过后，下一步（人类决定是否要做，不属于本次 Codex 任务）：下次重新跑生成
时观察 BackendExpert 是否还会选择模块级缓存连接的写法。
