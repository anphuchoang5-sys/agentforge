"""
backend_expert.py — 后端专家 Agent
B 核心产出物

接收任务描述 + 接口规范 → 用 DeepSeek 生成后端代码 → 写入磁盘
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from backend.graph.project_state import ProjectState
from backend.tools.file_tools import write_file
from backend.agents.experts.output_naming import resolve_output_dir

load_dotenv()

BACKEND_SYSTEM_PROMPT = """你是一位专业的 Python 后端工程师。
你的任务是根据接口规范，用 Python + SQLite 实现后端数据层代码。

要求：
- 使用标准库 sqlite3，不引入额外依赖
- 数据库文件名固定为 app.db
- 严格按照给定的函数名和参数实现，不要改名
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 代码要能直接运行，不留 TODO
"""


def _extract_code(text: str) -> str:
    """从模型回复中提取 ```python ... ``` 里的代码"""
    if "```python" in text:
        start = text.index("```python") + 9
        end = text.index("```", start)
        return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    return text.strip()


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

请实现完整的 Python 后端代码。"""

    llm = ChatOpenAI(
        model=os.getenv("EXPERT_MODEL", "deepseek-coder"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=0.2,
    )

    response = llm.invoke(
        [
            {"role": "system", "content": BACKEND_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )

    code = _extract_code(response.content)
    path = write_file(f"{app_output_dir}/db.py", code)

    print(f"[BackendExpert] 完成，代码已写入 {path}")
    return {"backend_code": code, "backend_path": path, "app_output_dir": app_output_dir}
