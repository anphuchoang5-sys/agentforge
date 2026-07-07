"""
schemas.py — 验证者 Agent 数据模型（对齐对外接口）
同学C 定义 · 定死不改

对外接口（B 调用 / D 展示）:
    validate(app_path) -> TestReport
    TestReport.model_dump() 直接 JSON 序列化即接口输出:
    {
        "passed": true,
        "logs": [...],
        "screenshot": "base64...",
        "failed_tests": [...]
    }
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class FailedTest(BaseModel):
    """单条失败项（结构化，供 D 展示 + B 的 fix_expert 读取）"""
    name: str = Field(description="失败项标识，如 'test_delete_todo' / 'ruff:F401' / 'compile'")
    reason: str = Field(description="失败原因说明")
    task_type: Optional[Literal["frontend", "backend", "test", "ui_validate"]] = Field(
        default=None,
        description="失败标准归属的任务类型；非 acceptance_criteria 比对产生的失败项（如 compile/ruff/pytest）为 None",
    )
    severity: Literal["error", "warning"] = Field(
        default="error",
        description="error=阻断（failed），warning=仅提示（不阻断 passed）",
    )


class TestReport(BaseModel):
    """测试报告（对外接口，定死不改）

    B 接收后判断是否触发修复循环；D 直接展示。
    """
    passed: bool = Field(description="四项检查是否全部通过（warning 不影响）")
    logs: List[str] = Field(
        default_factory=list,
        description="执行日志，按时间顺序，每条一句",
    )
    screenshot: str = Field(
        default="",
        description="base64 PNG，不带 data:image/png;base64, 前缀；无截图时为空串",
    )
    failed_tests: List[FailedTest] = Field(
        default_factory=list,
        description="失败项列表；passed=True 时为空",
    )

    # —— 以下为元数据，不影响接口契约，供 D 展示 + B 路由用 ——
    app_path: str = Field(default="", description="被验证的应用路径")
    app_type: str = Field(default="", description="应用类型：desktop / web / unknown")
    iteration: int = Field(default=0, description="当前修复轮次（由 B 传入）")

