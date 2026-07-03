"""
task_manager.py — 任务注册表 + 后台执行 + 事件推送
B 核心产出物

run() 是同步阻塞函数（真实调 LLM，耗时数十秒到几分钟），FastAPI 的
event loop 不能被它卡住，所以丢进线程池跑（asyncio.to_thread）；
执行过程中通过 on_event 回调把事件塞进 asyncio.Queue，
routes/websocket.py 再从 Queue 里读出来实时推给前端。

进程内存存储，重启即丢——两周演示项目不需要 Redis/数据库级任务队列。
"""

import asyncio
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.api.event_translator import EventTranslator
from backend.pipeline.run import run

END_SENTINEL = {"type": "__end__"}


@dataclass
class Task:
    task_id: str
    user_input: str
    queue: "asyncio.Queue" = field(default_factory=asyncio.Queue)
    done: bool = False


_tasks: dict[str, Task] = {}
_background_refs: set = set()  # 防止 asyncio.create_task 的任务被 GC 提前回收


def create_task(user_input: str) -> Task:
    task_id = uuid.uuid4().hex[:12]
    task = Task(task_id=task_id, user_input=user_input)
    _tasks[task_id] = task
    return task


def schedule(task: Task) -> None:
    """把任务丢进后台跑，调用方（路由层）不用关心 asyncio.create_task 的生命周期"""
    coro = run_pipeline_in_background(task)
    bg_task = asyncio.create_task(coro)
    _background_refs.add(bg_task)
    bg_task.add_done_callback(_background_refs.discard)


def get_task(task_id: str) -> Optional[Task]:
    return _tasks.get(task_id)


async def run_pipeline_in_background(task: Task) -> None:
    """调度到线程池跑 run()，实时把翻译后的 UI 事件推进 task.queue"""
    loop = asyncio.get_running_loop()
    translator = EventTranslator()

    def push(event: dict) -> None:
        loop.call_soon_threadsafe(task.queue.put_nowait, event)

    for event in translator.start():
        push(event)

    def on_event(node_name: str, node_output: dict) -> None:
        for event in translator.on_node(node_name, node_output):
            push(event)

    def run_sync() -> dict:
        return run(task.user_input, on_event=on_event)

    try:
        result = await asyncio.to_thread(run_sync)
        push({"type": "done", "result": result})
    except Exception as e:
        push({"type": "error", "message": str(e), "detail": traceback.format_exc()})
    finally:
        task.done = True
        push(END_SENTINEL)
