"""
task_manager.py — 任务注册表 + 后台执行 + 事件推送
B 核心产出物

run() 是同步阻塞函数（真实调 LLM，耗时数十秒到几分钟），FastAPI 的
event loop 不能被它卡住，所以丢进线程池跑（asyncio.to_thread）；
执行过程中通过 on_event 回调把事件同时记进 task.history（完整事件历史）
和广播给所有当前连接的 WebSocket 订阅者，routes/websocket.py 再实时推给前端。

之前是"一个任务配一个共享 Queue"，取过的事件就没了：任务跑完之后才连上的
客户端会在空 Queue 上永远卡住（problem.md 第28条），也没法让两个同时连接
的客户端各自看到完整日志流。现在改成"事件历史 + 每个连接各自的订阅 Queue"：
新连接先重放 history 补齐错过的部分，再实时接收后续事件；判断"任务是否已经
结束"不再依赖一个写了没人读的 done 字段，而是直接看 history 里有没有出现
过 END_SENTINEL，天然跟事件流保持一致。

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
    history: list = field(default_factory=list)          # 完整事件历史，供新连接重放
    subscribers: list = field(default_factory=list)       # 当前活跃 WebSocket 连接各自的 Queue


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


def subscribe(task: Task) -> "asyncio.Queue":
    """WebSocket 连接建立时调用：注册一个只属于这条连接的 Queue，
    之后每个新事件都会广播进所有当前订阅者的 Queue（而不是被某一个连接独占取走）"""
    q: "asyncio.Queue" = asyncio.Queue()
    task.subscribers.append(q)
    return q


def unsubscribe(task: Task, q: "asyncio.Queue") -> None:
    """WebSocket 连接断开时调用：从订阅列表里摘掉，避免持续给已断开的连接推事件"""
    if q in task.subscribers:
        task.subscribers.remove(q)


async def run_pipeline_in_background(task: Task) -> None:
    """调度到线程池跑 run()，实时把翻译后的 UI 事件记进历史 + 广播给所有订阅者"""
    loop = asyncio.get_running_loop()
    translator = EventTranslator()

    def push(event: dict) -> None:
        def _record_and_broadcast() -> None:
            task.history.append(event)
            for q in list(task.subscribers):
                q.put_nowait(event)
        # 这个回调本身从工作线程（asyncio.to_thread 里跑 run_sync）触发，
        # 用 call_soon_threadsafe 把"记历史 + 广播"整体丢回事件循环线程一次性做完，
        # 避免历史记录和某个订阅者的 Queue 之间出现不一致的中间状态
        loop.call_soon_threadsafe(_record_and_broadcast)

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
        push(END_SENTINEL)
