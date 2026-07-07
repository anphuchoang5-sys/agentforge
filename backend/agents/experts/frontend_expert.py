"""
frontend_expert.py — 前端专家 Agent
B 核心产出物

接收任务描述 + 接口规范 → 用 DeepSeek 生成 Tkinter 界面代码 → 写入磁盘
与 BackendExpert 并行执行（都读接口规范，不等对方）
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from backend.graph.project_state import ProjectState
from backend.tools.file_tools import write_file
from backend.tools.llm_logging import timed_invoke
from backend.agents.experts.output_naming import resolve_output_dir
from backend.skills.loader import load_skill_prompt

load_dotenv()

FRONTEND_SYSTEM_PROMPT = """你是一位专业的 Python 桌面 UI 工程师。
你的任务是根据接口规范，用 Python + Tkinter 实现桌面应用界面。

要求：
- 只用标准库 tkinter，不引入额外依赖
- 从 db 模块 import 函数（按接口规范的函数名）
- 界面要有：输入框、添加按钮、任务列表、删除按钮
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 代码要能直接运行，if __name__ == '__main__': 启动主循环
""" + "\n\n" + load_skill_prompt("build")


def _extract_code(text: str) -> str:
    if not text or not text.strip():
        raise RuntimeError("FrontendExpert 没有返回任何内容")
    if "```python" in text:
        start = text.index("```python") + 9
        end = text.index("```", start)
        code = text[start:end].strip()
        if not code:
            raise RuntimeError("FrontendExpert 返回了空 Python 代码块")
        return code
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        code = text[start:end].strip()
        if not code:
            raise RuntimeError("FrontendExpert 返回了空代码块")
        return code
    raise RuntimeError("FrontendExpert 未按约定返回 ```python ... ``` 代码块")


def _assert_tkinter_app(code: str) -> None:
    if "import tkinter" not in code and "from tkinter" not in code:
        raise RuntimeError("FrontendExpert 生成的代码不像 Tkinter 应用：缺少 tkinter import")
    if "mainloop(" not in code:
        raise RuntimeError("FrontendExpert 生成的代码缺少 mainloop()，不能证明 UI 会启动")


def frontend_expert_node(state: ProjectState) -> dict:
    """LangGraph 节点函数：生成前端界面代码并落盘

    读取：state["task_decomposition"]（接口规范）
    写入：state["frontend_code"]、state["frontend_path"]

    注意：不写 state["app_output_dir"]——本节点与 BackendExpert 并行执行，
    两边同时写同一个 key 会在 LangGraph 里冲突。resolve_output_dir() 是纯函数，
    这里独立算一遍即可，结果和 BackendExpert 算出来的必然一致。
    """
    print("[FrontendExpert] 开始生成前端代码...")
    decomp = state["task_decomposition"]
    app_output_dir = resolve_output_dir(state["output_base_dir"], decomp)

    api_spec_text = "\n".join(
        f"- {name}({', '.join(f'{p.name}:{p.type}' for p in spec.params)}) -> {spec.return_type}"
        for name, spec in decomp.api_spec.functions.items()
    )

    frontend_tasks = [t for t in decomp.tasks if t.type == "frontend"]
    task_desc = frontend_tasks[0].description if frontend_tasks else "实现桌面 UI"

    prompt = f"""任务：{task_desc}

可以调用的后端接口（从 db 模块 import）：
{api_spec_text}

请实现完整的 Tkinter 桌面应用代码。"""

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("FrontendExpert 缺少 DEEPSEEK_API_KEY，无法真实生成代码")

    llm = ChatOpenAI(
        model=os.getenv("EXPERT_MODEL", "deepseek-v4-pro"),
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=0.2,
    )

    response = timed_invoke(
        llm,
        [
            {"role": "system", "content": FRONTEND_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        caller="FrontendExpert",
    )

    code = _extract_code(response.content)
    _assert_tkinter_app(code)
    path = write_file(f"{app_output_dir}/app.py", code)

    print(f"[FrontendExpert] 完成，代码已写入 {path}")
    return {"frontend_code": code, "frontend_path": path}
