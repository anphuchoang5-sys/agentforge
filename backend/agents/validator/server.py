"""
server.py — 验证者 FastAPI 服务
同学C 核心产出物 · 对齐 B 的 validator_stub.py 接口

B 的 validator_stub.py 里已经写好了 HTTP 调用逻辑：
    requests.post(f"{VALIDATOR_URL}/validate", json={"app_path": app_path})
    期望返回: {"passed": true, "logs": [...], "screenshot": "base64...", "failed_tests": []}

启动方式:
    python -m backend.agents.validator.server
    或: uvicorn backend.agents.validator.server:app --host 0.0.0.0 --port 8901

B 接入方式（在 .env 加一行）:
    VALIDATOR_URL=http://localhost:8901
"""

import sys

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from .run import validate as _validate, health_check as _health_check

# Windows 默认控制台编码是 GBK，本文件和 _selftest.py 里的 print 用了 emoji
# （🚀✅❌等），GBK 编码不了会直接 UnicodeEncodeError 崩溃。之前是靠运行时
# 手动设置 PYTHONIOENCODING=utf-8 环境变量绕过的，忘记设就会复现崩溃
# （problem.md 第31条）。这里直接在代码里改流编码，不依赖任何人记得设环境变量。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    # stdout/stderr 被重定向成不支持 reconfigure 的流时（比如某些测试捕获场景），
    # 直接跳过——不影响功能，只是那种场景下本来就不会在真实控制台崩溃
    pass

app = FastAPI(
    title="AgentForge Validator",
    description="同学C · 验证者 Agent 服务（四项检查 + 桌面截图）",
    version="1.0.0",
)


# ── 请求/响应模型（对齐 B 的 validator_stub.py 接口） ──

class ValidateRequest(BaseModel):
    """B 调用时的请求体"""
    app_path: str = Field(description="应用入口文件路径，如 ./output/todo_app/app.py")
    criteria: Optional[List[str]] = Field(
        default=None,
        description="验收标准列表（来自 Commander 的 acceptance_criteria，可选）",
    )
    iteration: int = Field(default=0, description="修复轮次（由 B 传入）")


class FailedTestResponse(BaseModel):
    """失败项（对齐 B 期望的 failed_tests 格式）"""
    name: str
    reason: str
    severity: str = "error"


class ValidateResponse(BaseModel):
    """B 期望的返回格式：passed / logs / screenshot / failed_tests

    多出来的 app_path / app_type / iteration 字段 B 不读也不影响。
    """
    passed: bool
    logs: List[str] = []
    screenshot: str = ""
    failed_tests: List[FailedTestResponse] = []
    # 额外字段（B 不读，D 展示用）
    app_path: str = ""
    app_type: str = ""
    iteration: int = 0


# ── 接口 ──

@app.post("/validate", response_model=ValidateResponse)
def validate_endpoint(req: ValidateRequest) -> ValidateResponse:
    """验证者主接口 —— B 的 validator_stub.py 调的就是这个

    请求: POST /validate  {"app_path": "./output/todo_app/app.py"}
    返回: {"passed": true, "logs": [...], "screenshot": "base64...", "failed_tests": []}
    """
    try:
        report = _validate(
            app_path=req.app_path,
            criteria=req.criteria,
            iteration=req.iteration,
        )
    except Exception as e:
        # 保证异常时也返回结构化结果（B 不会因为 C 崩了而卡死）
        return ValidateResponse(
            passed=False,
            logs=[f"[validator] 内部异常: {type(e).__name__}: {str(e)[:300]}"],
            screenshot="",
            failed_tests=[FailedTestResponse(name="validator", reason=str(e)[:300])],
            app_path=req.app_path,
        )

    # TestReport → ValidateResponse（字段名一致，直接构造）
    return ValidateResponse(
        passed=report.passed,
        logs=report.logs,
        screenshot=report.screenshot,
        failed_tests=[
            FailedTestResponse(name=f.name, reason=f.reason, severity=f.severity)
            for f in report.failed_tests
        ],
        app_path=report.app_path,
        app_type=report.app_type,
        iteration=report.iteration,
    )


@app.get("/health")
def health_endpoint():
    """健康检查（D 的前端探活 / B 联调前自检）"""
    return _health_check()


# ── 本地启动 ──

if __name__ == "__main__":
    import uvicorn
    print("🚀 验证者服务启动: http://localhost:8901")
    print("   接口文档: http://localhost:8901/docs")
    print("   B 接入: .env 加 VALIDATOR_URL=http://localhost:8901")
    uvicorn.run(app, host="0.0.0.0", port=8901)
