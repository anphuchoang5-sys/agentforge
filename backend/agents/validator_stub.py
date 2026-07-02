"""
validator_stub.py — C 的接口桩
B 临时实现，等 C 完成后替换为真实调用

C 的对外接口（来自分工表）：
  输入：{"app_path": "./output/generated_app/app.py"}
  输出：{"passed": True, "logs": [...], "screenshot": "base64...", "failed_tests": []}

现在用简单的文件存在性检查 + 测试结果来判断是否通过。
等 C 的 FastAPI 服务上线后，把 validate() 里的逻辑换成 HTTP 调用即可。
"""

import os
import requests


def validate(app_path: str, test_results: str = "") -> dict:
    """调用 C 的验证接口，拿到测试报告

    当 C 的服务还没上线时，走本地 Mock 逻辑。
    C 上线后：把 VALIDATOR_URL 写进 .env，自动切换到真实调用。
    """
    validator_url = os.getenv("VALIDATOR_URL")

    if validator_url:
        # C 已上线，走真实接口
        try:
            resp = requests.post(
                f"{validator_url}/validate",
                json={"app_path": app_path},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[Validator] C 的服务调用失败，降级到 Mock: {e}")

    # Mock 逻辑：文件存在 + 测试没有 FAILED 就算通过
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
        logs.append("Mock 验证通过（等 C 上线后替换为真实验证）")

    print(f"[Validator] Mock 结果: {'通过' if passed else '失败'}")
    return {
        "passed": passed,
        "logs": logs,
        "screenshot": None,
        "failed_tests": [],
    }
