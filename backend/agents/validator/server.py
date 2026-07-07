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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from .run import validate as _validate, health_check as _health_check
from backend.tools.console_encoding import ensure_utf8_console

# 本文件和 _selftest.py 里的 print 用了 emoji（🚀✅❌等），Windows 默认 GBK
# 控制台编不了会直接 UnicodeEncodeError 崩溃（problem.md 第31条）。
ensure_utf8_console()

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
    criteria_task_type: Optional[dict[str, str]] = Field(
        default=None,
        description="验收标准文本到 Commander 任务类型的映射",
    )
    iteration: int = Field(default=0, description="修复轮次（由 B 传入）")
    code_content: Optional[str] = Field(
        default=None,
        description="调用方提供的完整代码内容，避免 Validator 自行截断读取",
    )
    pytest_result_path: Optional[str] = Field(
        default=None,
        description="pytest --json-report 输出路径，缺失时必须明确失败",
    )


class FailedTestResponse(BaseModel):
    """失败项（对齐 B 期望的 failed_tests 格式）"""
    name: str
    reason: str
    task_type: Optional[str] = None
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
            criteria_task_type=req.criteria_task_type,
            iteration=req.iteration,
            code_content=req.code_content,
            pytest_result_path=req.pytest_result_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Validator 真实执行失败: {type(e).__name__}: {str(e)[:300]}",
        ) from e

    # TestReport → ValidateResponse（字段名一致，直接构造）
    return ValidateResponse(
        passed=report.passed,
        logs=report.logs,
        screenshot=report.screenshot,
        failed_tests=[
            FailedTestResponse(name=f.name, reason=f.reason, task_type=f.task_type, severity=f.severity)
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
