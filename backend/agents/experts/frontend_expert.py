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
""" + "\n\n" + load_skill_prompt("build") + "\n\n" + load_skill_prompt("frontend-ui")


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


def _build_retry_feedback(state: ProjectState) -> str:
    """重试轮次里，把上一轮 Validator 判定失败的具体原因 + 上一轮生成的界面
    代码拼成一段反馈，让模型针对性修复界面问题，而不是对着同一份任务描述
    重新生成一遍一模一样的代码。

    只过滤掉明确标为 backend/test 的失败项；task_type 为 None 的项
    （compile/ruff 这类检查产生的失败，标不出确切归属）依然要给
    FrontendExpert 看。
    """
    failed_tests = state.get("failed_tests")
    if not failed_tests:
        return ""

    relevant_failures = [
        f for f in failed_tests
        if f.get("task_type") not in ("backend", "test")
    ]
    if not relevant_failures:
        return ""

    reasons = "\n".join(
        f"- [{f.get('name', '?')}] {f.get('reason', '')}"
        for f in relevant_failures
    )
    prev_code = state.get("frontend_code") or ""

    return f"""

⚠️ 这是修复轮次，上一轮生成的界面代码没有通过验证，具体失败原因如下（已经
过滤掉明确是后端/测试的部分，只保留跟界面相关或无法确定归属的失败原因）：
{reasons}

上一轮生成的前端代码：
```python
{prev_code}
```

请基于上述失败原因修复对应问题；已经正确、跟失败原因无关的部分不要无意义地大改。"""


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

请实现完整的 Tkinter 桌面应用代码。{_build_retry_feedback(state)}"""

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

    try:
        code = _extract_code(response.content)
        _assert_tkinter_app(code)
    except RuntimeError as e:
        # 重试轮次里 LLM 有可能不按约定返回（比如生成的代码不是 Tkinter 应用）；
        # 直接 raise 会绕过 should_retry 直接终止整条流程——这个节点现在会在
        # 重试轮次里被反复调用（见 workflow.py::should_retry），不再是"只跑一次"，
        # 跟 test_expert_node 已有的"不直接raise"原则保持一致：老实返回失败信号，
        # state 里的 frontend_code/frontend_path 保留上一轮的值不变，让重试闭环
        # 有机会下一轮重新尝试，而不是把整个任务判死刑
        print(f"[FrontendExpert] ❌ 本轮生成失败，保留上一轮代码: {e}")
        return {"frontend_generated": False}

    path = write_file(f"{app_output_dir}/app.py", code)

    print(f"[FrontendExpert] 完成，代码已写入 {path}")
    return {"frontend_code": code, "frontend_path": path, "frontend_generated": True}
