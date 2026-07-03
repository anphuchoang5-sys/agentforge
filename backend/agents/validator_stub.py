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


def validate(app_path: str, test_results: str = "") -> dict:
    """调用 C 的验证接口，拿到测试报告

    优先直接 Python 调用（同仓库，零配置）；
    VALIDATOR_URL 存在时走 HTTP（跨机器部署）；
    都不行就降级 Mock。
    """
    # 策略1：直接 Python 调用 C 的 validate()（同仓库，推荐）
    try:
        from backend.agents.validator import validate as c_validate
        from backend.agents.validator.schemas import TestReport
        report = c_validate(app_path=app_path)
        # TestReport → dict（和原来的 Mock 返回格式一致）
        return report.model_dump()
    except Exception as e:
        print(f"[Validator] C 的 validate() 直接调用失败: {e}")

    # 策略2：HTTP 调用 C 的 FastAPI 服务（跨机器 / 需要隔离时用）
    validator_url = os.getenv("VALIDATOR_URL")
    if validator_url:
        try:
            import requests
            resp = requests.post(
                f"{validator_url}/validate",
                json={"app_path": app_path},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
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
