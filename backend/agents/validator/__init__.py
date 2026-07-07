"""
validator — 同学C：自动化验证与桌面控制模块

对外接口（供 B 调用）:
    validate(app_path, criteria=None) -> TestReport
        → .passed            (bool)
        → .logs             (list[str])
        → .screenshot       (base64 PNG)
        → .failed_tests     (list[FailedTest])

    health_check() -> dict
        检查 pywinauto / ruff 依赖是否就绪

使用方式:
    from backend.agents.validator import validate
    report = validate("./output/todo_app/main.py")
    report.model_dump()  # → 接口 JSON

FastAPI 服务（B 的 validator_stub.py 通过 HTTP 调用）:
    python -m backend.agents.validator.server
    → http://localhost:8901/validate
    → http://localhost:8901/health
    B 接入: .env 加 VALIDATOR_URL=http://localhost:8901
"""

from .run import validate, health_check, detect_app_type
from .schemas import TestReport, FailedTest

__all__ = ["validate", "health_check", "detect_app_type", "TestReport", "FailedTest"]
