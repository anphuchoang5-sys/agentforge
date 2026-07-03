"""
event_translator.py — 把 LangGraph 节点完成事件翻译成前端 UI 事件
B 核心产出物

run(on_event=...) 每次只吐 (节点名, 该节点的增量dict)，这里翻译成
D 的 appStore.ts 真正需要的三种事件：log / node_status / progress。

节点名 → 前端 AgentId 映射（对应 workflow.py 的 graph.add_node 名称
和 frontend/src/store/appStore.ts 的 AgentId 类型）：
    decompose      → commander
    backend_expert → backend
    frontend_expert→ frontend
    test_expert    → test
    validator      → validator
    count          → 无对应 UI 节点，纯计数，不推送
    （uivalidator 目前没有对应的图节点——C 还没实现 UIValidator Agent，
      见 problem.md 第4条，这里永远不会推送 uivalidator 的状态更新，
      前端会一直显示 idle，这是如实反映现状，不是遗漏）
"""

import time


class EventTranslator:
    def __init__(self):
        self._backend_runs = 0
        self._frontend_done = False
        self._max_progress = 0

    # ── 任务开始时调用一次 ──────────────────────────────────────
    def start(self) -> list[dict]:
        return [
            self._log("System", "AgentForge 开始处理需求", "info"),
            self._status("commander", "running"),
        ]

    # ── 每次收到节点完成事件调用一次 ────────────────────────────
    def on_node(self, node_name: str, output: dict) -> list[dict]:
        handler = getattr(self, f"_on_{node_name}", None)
        if handler is None:
            return []
        return handler(output)

    def _on_decompose(self, output: dict) -> list[dict]:
        decomp = output.get("task_decomposition")
        app_name = getattr(decomp, "app_name", None) or "未命名"
        n_tasks = len(getattr(decomp, "tasks", None) or [])
        events = [
            self._log("Commander", f"需求拆解完成，应用名: {app_name}，共 {n_tasks} 个子任务", "success"),
            self._status("commander", "success"),
            self._status("backend", "running"),
            self._status("frontend", "running"),
            self._log("System", "BackendExpert 和 FrontendExpert 并行启动", "info"),
        ]
        events.append(self._progress(15))
        return events

    def _on_backend_expert(self, output: dict) -> list[dict]:
        self._backend_runs += 1
        events = []
        if self._backend_runs > 1:
            events.append(self._log("System", f"第 {self._backend_runs - 1} 轮修复开始", "warn"))
            events.append(self._status("test", "idle"))
            events.append(self._status("validator", "idle"))
        path = output.get("backend_path")
        events.append(self._log("BackendExpert", f"后端代码生成完成: {path}", "success"))
        events.append(self._status("backend", "success"))
        if self._frontend_done:
            events.append(self._status("test", "running"))
        return events

    def _on_frontend_expert(self, output: dict) -> list[dict]:
        self._frontend_done = True
        path = output.get("frontend_path")
        events = [
            self._log("FrontendExpert", f"前端代码生成完成: {path}", "success"),
            self._status("frontend", "success"),
        ]
        if self._backend_runs >= 1:
            events.append(self._status("test", "running"))
        events.append(self._progress(45))
        return events

    def _on_test_expert(self, output: dict) -> list[dict]:
        passed = output.get("test_passed")
        path = output.get("test_path")
        level = "success" if passed else "warn"
        events = [
            self._log("TestExpert", f"测试{'通过' if passed else '失败'}: {path}", level),
            self._status("test", "success" if passed else "error"),
            self._status("validator", "running"),
        ]
        events.append(self._progress(75))
        return events

    def _on_validator(self, output: dict) -> list[dict]:
        passed = output.get("validation_passed")
        logs = output.get("validation_logs") or []
        events = [self._log("Validator", str(line), "info") for line in logs]
        if passed:
            events.append(self._log("Validator", "验证通过", "success"))
            events.append(self._status("validator", "success"))
            events.append(self._progress(100))
        else:
            events.append(self._log("Validator", "验证未通过，准备重试", "warn"))
            events.append(self._status("validator", "error"))
        return events

    def _on_count(self, output: dict) -> list[dict]:
        return []  # 纯计数节点，无对应 UI 节点

    # ── 事件构造小工具 ──────────────────────────────────────────
    def _log(self, agent: str, message: str, level: str = "info") -> dict:
        # timestamp 用毫秒时间戳，对齐 appStore.ts LogEntry.timestamp（new Date(ms) 直接能用）
        return {
            "type": "log",
            "agent": agent,
            "message": message,
            "level": level,
            "timestamp": int(time.time() * 1000),
        }

    def _status(self, id_: str, status: str) -> dict:
        return {"type": "node_status", "id": id_, "status": status}

    def _progress(self, value: int) -> dict:
        self._max_progress = max(self._max_progress, value)
        return {"type": "progress", "progress": self._max_progress}
