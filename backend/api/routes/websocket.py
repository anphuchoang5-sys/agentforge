"""
routes/websocket.py — 实时事件推送
B 核心产出物 · 对齐最终分工表接口④（所有人 → D 的进度推送）
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.task_manager import END_SENTINEL, get_task, subscribe, unsubscribe

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/tasks/{task_id}")
async def ws_task_events(websocket: WebSocket, task_id: str) -> None:
    task = get_task(task_id)
    if task is None:
        await websocket.close(code=4404, reason="task not found")
        return

    await websocket.accept()
    # 先订阅再拍快照：subscribe()和下面的 list(task.history) 之间没有任何
    # await，asyncio 单线程协作式调度不会在这两行之间插入别的协程执行，
    # 保证不会有事件被漏发或重复发（既不在快照里也不在订阅队列里，
    # 或者两边都有导致重复推送）
    q = subscribe(task)
    try:
        # 重放这条连接建立之前已经发生的事件——处理"任务已经跑完/跑到一半
        # 才连上"的情况：以前直接对着共享 Queue 等，Queue 早被别的连接取空了，
        # 会永远卡住（problem.md 第28条）
        already_finished = False
        for event in list(task.history):
            if event == END_SENTINEL:
                already_finished = True
                break
            await websocket.send_json(event)

        if not already_finished:
            while True:
                event = await q.get()
                if event == END_SENTINEL:
                    break
                await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(task, q)
        await websocket.close()
