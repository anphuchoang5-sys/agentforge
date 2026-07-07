"""
backend_expert.py — 后端专家 Agent
B 核心产出物

接收任务描述 + 接口规范 → 用 DeepSeek 生成后端代码 → 写入磁盘
"""

import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from backend.graph.project_state import ProjectState
from backend.tools.file_tools import write_file
from backend.tools.llm_logging import timed_invoke
from backend.agents.experts.output_naming import resolve_output_dir
from backend.skills.loader import load_skill_prompt

load_dotenv()

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


def _extract_code(text: str) -> str:
    """从模型回复中提取 ```python ... ``` 里的代码"""
    if not text or not text.strip():
        raise RuntimeError("BackendExpert 没有返回任何内容")
    if "```python" in text:
        start = text.index("```python") + 9
        end = text.index("```", start)
        code = text[start:end].strip()
        if not code:
            raise RuntimeError("BackendExpert 返回了空 Python 代码块")
        return code
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        code = text[start:end].strip()
        if not code:
            raise RuntimeError("BackendExpert 返回了空代码块")
        return code
    raise RuntimeError("BackendExpert 未按约定返回 ```python ... ``` 代码块")


def _assert_api_functions_exist(code: str, decomp, required_names: "list[str] | None" = None) -> None:
    """校验生成的 db.py 是否实现了所有必须的函数。

    默认只对照 Commander 最初的 api_spec；重试轮次还会传入
    `required_names`（app.py 实际 import 的函数名，见 `_extract_frontend_imports`），
    因为 FrontendExpert 在重试时不会重新生成，app.py 的 import 语句才是这份
    db.py 到底要满足谁的"事实真相"，比一开始的 api_spec 更贴近会不会
    ImportError。
    """
    names = set(decomp.api_spec.functions) | set(required_names or [])
    missing = [
        name for name in names
        if f"def {name}(" not in code and f"async def {name}(" not in code
    ]
    if missing:
        raise RuntimeError(
            "BackendExpert 生成的代码没有真实实现接口函数: "
            + ", ".join(missing)
        )


def _extract_frontend_imports(frontend_code: str) -> "list[str]":
    """从 app.py 源码里解析出它实际从 db 模块 import 的函数名清单。

    重试时 BackendExpert 只重新生成 db.py，FrontendExpert 不会重新跑
    （retry 边只回 backend_expert，见 workflow.py），如果这一轮生成的函数
    签名和已经写死的 app.py import 对不上，应用启动会立刻 ImportError。
    只靠 Commander 最初的 api_spec 做参照不够可靠——api_spec 是"应该实现
    什么"，app.py 里的 import 才是"这份代码实际会被谁调用、调用哪些名字"
    的真相来源，两者理论上该一致但 LLM 生成时可能跑偏。
    """
    names: list[str] = []
    for match in re.finditer(r"from\s+\.?db\s+import\s+(\([^)]*\)|[^\n]+)", frontend_code):
        block = match.group(1).strip().lstrip("(").rstrip(")")
        for part in block.split(","):
            part = part.strip()
            if not part:
                continue
            name = part.split(" as ")[0].strip()
            if name.isidentifier():
                names.append(name)
    return names


def _build_retry_feedback(state: ProjectState) -> str:
    """重试轮次里，把上一轮 Validator 判定失败的具体原因 + 上一轮生成的代码
    拼成一段反馈，让模型针对性修复，而不是对着同一份任务描述重新赌一次
    （problem.md 第47条）。

    第一次生成时 Validator 还没跑过，state["failed_tests"] 是空的，返回
    空字符串，prompt 跟原来完全一样。

    failed_tests 是 Validator 对整份代码（编译/ruff/pytest/全部验收标准）
    的失败清单，不只是后端的锅——有的可能是前端界面或测试用例的问题。
    不去猜哪条该过滤（problem.md 第42条：目前的数据结构猜不准哪条标准属于
    哪个专家），全部给模型看，交给它自己判断哪些是这份后端代码能修的。
    """
    failed_tests = state.get("failed_tests")
    if not failed_tests:
        return ""

    reasons = "\n".join(
        f"- [{f.get('name', '?')}] {f.get('reason', '')}"
        for f in failed_tests
    )
    prev_code = state.get("backend_code") or ""

    import_constraint = ""
    frontend_code = state.get("frontend_code")
    if frontend_code:
        imported_names = _extract_frontend_imports(frontend_code)
        if imported_names:
            import_constraint = f"""

⚠️ 硬约束：前端 app.py 本轮不会重新生成，它已经写死从 db 模块 import 了以下函数，
你重新生成的 db.py 必须原样提供这些函数（函数名、大小写完全一致，一个都不能少），
否则应用启动时会直接 ImportError：
{', '.join(imported_names)}
"""

    return f"""

⚠️ 这是修复轮次，上一轮生成的代码没有通过验证，具体失败原因如下（可能包含
不属于后端职责范围的项，比如前端界面或测试用例相关的失败，跳过即可，只处理
你能通过修改这份后端代码解决的部分）：
{reasons}
{import_constraint}
上一轮生成的后端代码：
```python
{prev_code}
```

请基于上述失败原因修复对应问题；已经正确、跟失败原因无关的部分不要无意义地大改。"""


def backend_expert_node(state: ProjectState) -> dict:
    """LangGraph 节点函数：生成后端代码并落盘

    读取：state["task_decomposition"]（A 的拆解结果）
    写入：state["backend_code"]、state["backend_path"]、state["app_output_dir"]
        （BackendExpert → TestExpert 是顺序依赖，输出目录在这里解析一次写回白板，
        TestExpert 直接读即可；FrontendExpert 并行执行，自己独立算一遍，见 output_naming.py）
    """
    print("[BackendExpert] 开始生成后端代码...")
    decomp = state["task_decomposition"]
    app_output_dir = resolve_output_dir(state["output_base_dir"], decomp)

    # 把接口规范格式化给模型看
    api_spec_text = "\n".join(
        f"- {name}({', '.join(f'{p.name}:{p.type}' for p in spec.params)}) -> {spec.return_type}"
        for name, spec in decomp.api_spec.functions.items()
    )

    # 找到 backend 类型的任务描述
    backend_tasks = [t for t in decomp.tasks if t.type == "backend"]
    task_desc = backend_tasks[0].description if backend_tasks else "实现后端数据层"

    prompt = f"""任务：{task_desc}

接口规范（你必须实现以下函数，函数名和参数不能改）：
{api_spec_text}

请实现完整的 Python 后端代码。{_build_retry_feedback(state)}"""

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("BackendExpert 缺少 DEEPSEEK_API_KEY，无法真实生成代码")

    llm = ChatOpenAI(
        model=os.getenv("EXPERT_MODEL", "deepseek-v4-pro"),
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=0.2,
    )

    response = timed_invoke(
        llm,
        [
            {"role": "system", "content": BACKEND_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        caller="BackendExpert",
    )

    code = _extract_code(response.content)
    frontend_code = state.get("frontend_code")
    required_names = _extract_frontend_imports(frontend_code) if frontend_code else None
    _assert_api_functions_exist(code, decomp, required_names)
    path = write_file(f"{app_output_dir}/db.py", code)

    print(f"[BackendExpert] 完成，代码已写入 {path}")
    return {"backend_code": code, "backend_path": path, "app_output_dir": app_output_dir}
