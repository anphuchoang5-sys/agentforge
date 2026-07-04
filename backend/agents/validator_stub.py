"""
validator_stub.py — C 的验证接口调用
B 临时实现 → C 已替换为真实调用

C 的对外接口（来自分工表）：
  输入：{"app_path": "./output/generated_app/app.py"}
  输出：{"passed": True, "logs": [...], "screenshot": "base64...", "failed_tests": []}

优先级：
  1. 直接 Python 调用 C 的 validate()（同仓库，无需 HTTP）
  2. HTTP 调用 C 的 FastAPI 服务（跨机器 / 微服务部署时用）
  3. 本地 Mock（C 不可用时降级）
"""

import os
from typing import List, Optional


def validate(
    app_path: str,
    test_results: str = "",
    criteria: Optional[List[str]] = None,
    code_content: Optional[str] = None,
    pytest_result_path: Optional[str] = None,
) -> dict:
    """调用 C 的验证接口，拿到测试报告

    优先直接 Python 调用（同仓库，零配置）；
    VALIDATOR_URL 存在时走 HTTP（跨机器部署）；
    都不行就降级 Mock。

    criteria: Commander 拆解出的验收标准（来自 task_decomposition.tasks[].acceptance_criteria，
        由 workflow.py::validator_node 拍平后传入），转发给 C 的 llm_check 逐条核对。
    code_content: workflow.py::validator_node 从 ProjectState 里拼好的完整代码
        （backend_code + frontend_code + test_code），转发给 C 避免她重新读硬盘+截断
        （见 problem.md 第16条）。
    pytest_result_path: TestExpert 用 `pytest --json-report` 生成的 JSON 报告路径，
        转发给 C 读取真实测试结果（见 problem.md 第17条）。
    """
    # 策略1：直接 Python 调用 C 的 validate()（同仓库，推荐）
    #
    # 只在"C 的模块导入失败"（环境没装好，比如 pywinauto 缺失）时才降级到
    # 策略2/3——一旦导入成功，真正调用 c_validate() 就不再包 try/except。
    # 之前这里是 except Exception 一网打尽，导致 C 的 validate() 内部真实
    # 抛出的业务 bug 会被当成"C 不可用"处理，悄悄落到下面策略3的简陋 Mock
    # 上，Mock 只查"文件存不存在"+"文本里有没有'failed'字样"就能编出一个
    # passed=True——这正是 CLAUDE.md 明确禁止的"静默兜底成假成功"
    # （problem.md 第27条）。现在的原则是：环境不可用 → 合理降级；
    # 代码本身报错 → 必须原样往上抛，让调用方看到真实失败，不能被吃掉。
    try:
        from backend.agents.validator import validate as c_validate
    except ImportError as e:
        print(f"[Validator] C 的验证模块导入失败（环境未就绪），降级到策略2/3: {e}")
    else:
        report = c_validate(
            app_path=app_path,
            criteria=criteria,
            code_content=code_content,
            pytest_result_path=pytest_result_path,
        )
        # TestReport → dict（和原来的 Mock 返回格式一致）
        return report.model_dump()

    # 策略2：HTTP 调用 C 的 FastAPI 服务（跨机器 / 需要隔离时用）
    # 同理：只有"连不上/网络层失败"才降级，C 服务返回的真实错误响应
    # （resp.raise_for_status() 抛出的 HTTPError）也算网络层失败，会降级；
    # 但如果 C 的服务返回了格式错误的 JSON，那是她那边的真 bug，
    # resp.json() 抛出的 JSONDecodeError 不在 RequestException 之内，会原样往上抛
    validator_url = os.getenv("VALIDATOR_URL")
    if validator_url:
        try:
            import requests
            resp = requests.post(
                f"{validator_url}/validate",
                json={"app_path": app_path, "criteria": criteria},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"[Validator] C 的 HTTP 服务调用失败，降级到 Mock: {e}")

    # 策略3：本地 Mock 降级
    app_exists = os.path.exists(app_path) if app_path else False
    test_results = test_results or ""
    tests_ok = "failed" not in test_results.lower() and "error" not in test_results.lower()

    passed = app_exists and tests_ok
    logs = []
    if not app_exists:
        logs.append(f"文件不存在: {app_path}")
    if not tests_ok:
        logs.append("测试有失败项")
    if passed:
        logs.append("Mock 验证通过（C 的模块不可用，走降级逻辑）")

    print(f"[Validator] Mock 降级结果: {'通过' if passed else '失败'}")
    return {
        "passed": passed,
        "logs": logs,
        "screenshot": None,
        "failed_tests": [],
    }
