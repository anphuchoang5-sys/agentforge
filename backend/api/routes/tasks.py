"""
routes/tasks.py — 任务提交 REST API
B 核心产出物 · 对齐最终分工表接口②的入口形状
"""

from fastapi import APIRouter

from backend.api.schemas import SubmitRequest, SubmitResponse
from backend.api.task_manager import create_task, schedule

router = APIRouter(prefix="/api", tags=["tasks"])


@router.post("/submit", response_model=SubmitResponse)
async def submit(req: SubmitRequest) -> SubmitResponse:
    """接收前端提交的需求，立刻返回 task_id，实际生成在后台跑，
    进度通过 WS /ws/tasks/{task_id} 推送。"""
    task = create_task(req.user_input)
    schedule(task)
    return SubmitResponse(task_id=task.task_id)
