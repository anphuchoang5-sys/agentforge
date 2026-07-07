"""
validator_stub.py — C 的验证接口调用
B 临时实现 → C 已替换为真实调用

C 的对外接口（来自分工表）：
  输入：{"app_path": "./output/generated_app/app.py"}
  输出：{"passed": True, "logs": [...], "screenshot": "base64...", "failed_tests": []}

优先级：
  1. VALIDATOR_URL 存在时调用 C 的 FastAPI 服务（跨机器 / 微服务部署）
  2. 否则直接 Python 调用 C 的 validate()（同仓库）

violent 分支原则：验证器不可用就是系统错误，必须明确报错；禁止 Mock、降级、
伪造通过。
"""

from typing import List, Optional
import os


def validate(
    app_path: str,
    test_results: str = "",
    criteria: Optional[List[str]] = None,
    criteria_task_type: Optional[dict[str, str]] = None,
    code_content: Optional[str] = None,
    pytest_result_path: Optional[str] = None,
) -> dict:
    """调用 C 的验证接口，拿到测试报告

    VALIDATOR_URL 存在时走 HTTP（跨机器部署），否则直接 Python 调用。
    任一路径失败都抛出明确异常，不再降级 Mock。

    criteria: Commander 拆解出的验收标准（来自 task_decomposition.tasks[].acceptance_criteria，
        由 workflow.py::validator_node 拍平后传入），转发给 C 的 llm_check 逐条核对。
    code_content: workflow.py::validator_node 从 ProjectState 里拼好的完整代码
        （backend_code + frontend_code + test_code），转发给 C 避免她重新读硬盘+截断
        （见 problem.md 第16条）。
    pytest_result_path: TestExpert 用 `pytest --json-report` 生成的 JSON 报告路径，
        转发给 C 读取真实测试结果（见 problem.md 第17条）。
    """
    validator_url = os.getenv("VALIDATOR_URL")
    if validator_url:
        try:
            import requests
            resp = requests.post(
                f"{validator_url}/validate",
                json={
                    "app_path": app_path,
                    "criteria": criteria,
                    "criteria_task_type": criteria_task_type,
                    "code_content": code_content,
                    "pytest_result_path": pytest_result_path,
                },
                timeout=(5, 240),
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"C 的 HTTP 验证服务调用失败: {e}") from e

    try:
        from backend.agents.validator import validate as c_validate
    except ImportError as e:
        raise RuntimeError(
            "C 的验证模块导入失败，无法执行真实 Validator。"
            "请安装依赖并修复环境，而不是使用 Mock 降级。"
        ) from e

    report = c_validate(
        app_path=app_path,
        criteria=criteria,
        criteria_task_type=criteria_task_type,
        code_content=code_content,
        pytest_result_path=pytest_result_path,
    )
    return report.model_dump()
