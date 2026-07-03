"""
test_expert.py — 测试专家 Agent
B 核心产出物

读取 backend_code → 生成 pytest 测试 → 真实运行 → 把结果写进白板
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from backend.graph.project_state import ProjectState
from backend.tools.file_tools import write_file
from backend.tools.command_tools import run_command
from backend.tools.llm_logging import timed_invoke

load_dotenv()

TEST_SYSTEM_PROMPT = """你是一位专业的 Python 测试工程师。
你的任务是为给定的后端代码编写 pytest 单元测试。

要求：
- 用 pytest 框架
- 覆盖主要函数的正常流程和边界情况
- 每个测试函数名以 test_ 开头
- 测试前用 fixture 初始化数据库，测试后清理
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 不要 import 不存在的模块
"""


def _extract_code(text: str) -> str:
    if "```python" in text:
        start = text.index("```python") + 9
        end = text.index("```", start)
        return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    return text.strip()


def test_expert_node(state: ProjectState) -> dict:
    """LangGraph 节点：生成测试代码并真实运行

    读取：state["backend_code"]、state["task_decomposition"]（取 type=="test" 的任务描述）
    写入：state["test_code"]、state["test_path"]、state["test_results"]、state["test_passed"]、
        state["pytest_report_path"]（JSON 格式，供 C 的 pytest_check 读取真实测试结果，
        不再是"跑了但没人看"的状态，见 problem.md 第17条）
    """
    print("[TestExpert] 开始生成测试代码...")

    backend_code = state.get("backend_code", "")
    if not backend_code:
        return {
            "test_code": None,
            "test_path": None,
            "test_results": "跳过：后端代码不存在",
            "test_passed": False,
            "pytest_report_path": None,
        }

    decomp = state["task_decomposition"]
    test_tasks = [t for t in decomp.tasks if t.type == "test"]
    task_desc = test_tasks[0].description if test_tasks else "覆盖主要函数的正常流程和边界情况"

    prompt = f"""任务：{task_desc}

请为以下后端代码编写 pytest 测试：

```python
{backend_code}
```

注意：测试文件会和 db.py 放在同一个目录下运行。"""

    llm = ChatOpenAI(
        model=os.getenv("EXPERT_MODEL", "deepseek-coder"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        temperature=0.1,
    )

    response = timed_invoke(
        llm,
        [
            {"role": "system", "content": TEST_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        caller="TestExpert",
    )

    test_code = _extract_code(response.content)
    test_path = write_file(f"{state['app_output_dir']}/test_app.py", test_code)

    # 真实运行 pytest，顺带生成 JSON 格式报告（--json-report）供 C 的 pytest_check 读取，
    # 不然 C 那边永远拿不到结构化的真实测试结果，只能靠桩函数跳过
    print("[TestExpert] 运行 pytest...")
    report_filename = "pytest_report.json"
    result = run_command(
        f"python -m pytest test_app.py -v --tb=short --json-report --json-report-file={report_filename}",
        cwd=state["app_output_dir"],
        timeout=30,
    )

    test_results = result["stdout"] + result["stderr"]
    test_passed = result["success"]
    report_path = f"{state['app_output_dir']}/{report_filename}"
    pytest_report_path = report_path if os.path.exists(report_path) else None

    print(f"[TestExpert] 测试{'通过' if test_passed else '失败'}")
    return {
        "test_code": test_code,
        "test_path": test_path,
        "test_results": test_results,
        "test_passed": test_passed,
        "pytest_report_path": pytest_report_path,
    }
