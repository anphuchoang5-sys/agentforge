"""
schemas.py — API 层 Pydantic 请求/响应模型
B 核心产出物

对齐最终分工表接口②的输入形状，以及 D 的 mockWebSocket.ts/appStore.ts
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
