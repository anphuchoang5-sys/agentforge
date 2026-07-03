"""
routes/websocket.py — 实时事件推送
B 核心产出物 · 对齐最终分工表接口④（所有人 → D 的进度推送）
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.task_manager import END_SENTINEL, get_task

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/tasks/{task_id}")
async def ws_task_events(websocket: WebSocket, task_id: str) -> None:
    task = get_task(task_id)
    if task is None:
        await websocket.close(code=4404, reason="task not found")
        return

    await websocket.accept()
    try:
        while True:
            event = await task.queue.get()
            if event == END_SENTINEL:
                break
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
