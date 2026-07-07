"""
schemas.py — API 层 Pydantic 请求/响应模型
B 核心产出物

对齐最终分工表接口②的输入形状，以及 D 的 appStore.ts
真实需要的推送事件形状（比 CLAUDE.md 里 {"step":..., "progress":...}
的极简示例更细，因为 D 的 Zustand store 需要区分日志/节点状态/进度三种更新）。
"""

from typing import Literal, Optional
from pydantic import BaseModel


class SubmitRequest(BaseModel):
    user_input: str


class SubmitResponse(BaseModel):
    task_id: str


# ── WebSocket 推送事件（对应 appStore.ts 的三个 action + 结束信号）──────────

class LogEvent(BaseModel):
    type: Literal["log"] = "log"
    agent: str
    message: str
    level: Literal["info", "warn", "error", "success"] = "info"
    timestamp: int  # 毫秒时间戳，对齐 appStore.ts LogEntry.timestamp


class NodeStatusEvent(BaseModel):
    type: Literal["node_status"] = "node_status"
    id: Literal["commander", "backend", "frontend", "test", "uivalidator", "validator"]
    status: Literal["idle", "running", "success", "error"]


class ProgressEvent(BaseModel):
    type: Literal["progress"] = "progress"
    progress: int


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    result: dict


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    detail: Optional[str] = None


class ValidatorResultEvent(BaseModel):
    """C 的 Validator 原始结果，逐轮和 done 事件里都会出现——故意不带 type
    字段，前端 agentClient.ts 的 isValidatorPayload() 按"有布尔 passed"识别，
    不看 type（历史原因：C 的 HTTP 接口本来就是这个扁平形状，直接透传）"""
    passed: bool
    logs: list[str] = []
    screenshot: str = ""
    failed_tests: list[dict] = []
    iteration: int = 0
    app_path: str = ""
    app_type: str = ""
