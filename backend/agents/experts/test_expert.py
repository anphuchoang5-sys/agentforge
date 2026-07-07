"""
test_expert.py — 测试专家 Agent
B 核心产出物

读取 backend_code → 生成 pytest 测试 → collect-only 验证 → 真实运行 → 把结果写进白板
"""

import os
import re
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from backend.graph.project_state import ProjectState
from backend.tools.file_tools import write_file
from backend.tools.command_tools import run_command
from backend.tools.llm_logging import timed_invoke
from backend.skills.loader import load_skill_prompt

load_dotenv()

TEST_SYSTEM_PROMPT = """你是一位专业的 Python 测试工程师。
你的任务是为给定的后端代码编写 pytest 单元测试。

要求：
- 用 pytest 框架
- 覆盖主要函数的正常流程和边界情况
- 参考用户提示里的完整验收标准，但只覆盖适合后端单元测试验证的部分
- 每个测试函数名以 test_ 开头
- 测试前用 fixture 初始化数据库，测试后清理
- 只输出 Python 代码，用 ```python ... ``` 包裹
- 不要 import 不存在的模块
""" + "\n\n" + load_skill_prompt("test")


def _extract_code(text: str) -> str:
    if not text or not text.strip():
        raise RuntimeError("TestExpert 没有返回任何内容")
    if "```python" in text:
        start = text.index("```python") + 9
        end = text.index("```", start)
        code = text[start:end].strip()
        if not code:
            raise RuntimeError("TestExpert 返回了空 Python 代码块")
        return code
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        code = text[start:end].strip()
        if not code:
            raise RuntimeError("TestExpert 返回了空代码块")
        return code
    raise RuntimeError("TestExpert 未按约定返回 ```python ... ``` 代码块")


def _format_task_context(decomp) -> str:
    """Format all tasks and criteria for the test-generation prompt."""
    task_lines = []
    criteria_lines = []

    for task in decomp.tasks:
        task_lines.append(f"- [{task.type}] {task.id}: {task.description}")
        for criterion in task.acceptance_criteria:
            criteria_lines.append(f"- [{task.type}] {criterion}")

    tasks_text = "\n".join(task_lines) if task_lines else "- (no tasks provided)"
    criteria_text = "\n".join(criteria_lines) if criteria_lines else "- (no acceptance criteria provided)"
    return f"""All Commander tasks:
{tasks_text}

Complete acceptance criteria from Commander:
{criteria_text}"""


def test_expert_node(state: ProjectState) -> dict:
    """LangGraph 节点：生成测试代码并真实运行

    读取：state["backend_code"]、state["task_decomposition"]（使用所有任务的验收标准）
    写入：state["test_code"]、state["test_path"]、state["test_results"]、state["test_passed"]、
        state["pytest_report_path"]（JSON 格式，供 C 的 pytest_check 读取真实测试结果，
        不再是"跑了但没人看"的状态，见 problem.md 第17条）
    """
    print("[TestExpert] 开始生成测试代码...")

    backend_code = state.get("backend_code", "")
    if not backend_code:
        # 不直接 raise：这个失败本身可以靠重试闭环解决（下一轮 BackendExpert 重新生成
        # 代码后，test_expert 会跟着重跑），raise 会绕过 should_retry 直接炸掉整条流程，
        # 白白浪费剩余的重试预算（对齐 problem.md 第39/#验证第2条的复核结论）
        return {
            "test_code": None,
            "test_path": None,
            "test_results": "跳过：后端代码不存在",
            "test_passed": False,
            "pytest_report_path": None,
        }

    decomp = state["task_decomposition"]
    task_context = _format_task_context(decomp)

    prompt = f"""{task_context}

请为以下后端代码编写 pytest 测试。

上面是完整验收标准。请真正参考这些标准：其中能用后端单元测试验证的部分（例如返回值、数据持久化、状态变更、边界输入）请覆盖；界面展示、窗口布局、按钮点击等 UI 交互类标准跳过即可，不要为了 UI 交互启动阻塞的 Tkinter mainloop，也不要强行要求 pytest 覆盖全部标准。

Backend code already generated as db.py:

```python
{backend_code}
```

注意：测试文件会和 db.py 放在同一个目录下运行。"""

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("TestExpert 缺少 DEEPSEEK_API_KEY，无法真实生成测试")

    llm = ChatOpenAI(
        model=os.getenv("EXPERT_MODEL", "deepseek-v4-pro"),
        api_key=api_key,
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
    if "def test_" not in test_code:
        raise RuntimeError("TestExpert 生成的代码没有任何 def test_ 测试函数")
    test_path = write_file(f"{state['app_output_dir']}/test_app.py", test_code)

    # ── collect-only 验证：生成后立即检查测试是否可被 pytest 发现 ──
    # 如果收集到 0 个测试 → LLM 生成的是无效测试代码 → 直接返回失败，触发重试
    print("[TestExpert] 验证测试收集（--collect-only）...")
    collect_result = run_command(
        "python -m pytest --collect-only -q",
        cwd=state["app_output_dir"],
        timeout=15,
    )
    collect_output = collect_result["stdout"] + collect_result["stderr"]

    # 从输出中提取 "collected N items" 或 "no tests collected"
    collected_match = re.search(r"collected\s+(\d+)\s+items?", collect_output)
    if collected_match:
        test_count = int(collected_match.group(1))
    elif "no tests" in collect_output.lower():
        test_count = 0
    else:
        # 兜底：统计带有 "::" 的行数（每条代表一个测试函数）
        test_lines = [l for l in collect_output.splitlines() if "::" in l and not l.strip().startswith("=")]
        test_count = len(test_lines)

    print(f"[TestExpert] collect-only: 收集到 {test_count} 个测试")

    if test_count == 0:
        error_msg = (
            f"[TestExpert] ❌ 测试生成失败：pytest 未收集到任何测试用例。"
            f"LLM 生成的代码中可能没有以 test_ 开头的函数，或存在语法错误导致 pytest 无法解析。"
            f"\n--- 生成的测试代码 ---\n{test_code[:800]}"
        )
        print(error_msg)
        # 不直接 raise：这一轮 LLM 生成的测试代码有问题，下一轮 BackendExpert 重新生成
        # 代码后 test_expert 会跟着重跑，有机会在重试轮次内自然修好，raise 会绕过
        # should_retry 直接终止整条流程，白白浪费重试预算
        return {
            "test_code": test_code,
            "test_path": test_path,
            "test_results": f"collect-only 失败：收集到 0 个测试\n{collect_output[:1000]}",
            "test_passed": False,
            "pytest_report_path": None,
        }

    # ── 测试收集通过，真实运行 pytest ──
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
    if not pytest_report_path:
        # 不直接 raise：报告文件没生成本身也是"这一轮没跑成功"的一种表现，交给
        # test_passed=False 走正常重试闭环，而不是让整条流程直接崩溃退出
        test_passed = False
        test_results += "\n[TestExpert] ⚠️ pytest 未生成 JSON 报告，视为本轮未通过"

    print(f"[TestExpert] 测试{'通过' if test_passed else '失败'}")
    return {
        "test_code": test_code,
        "test_path": test_path,
        "test_results": test_results,
        "test_passed": test_passed,
        "pytest_report_path": pytest_report_path,
    }
