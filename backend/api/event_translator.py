"""
event_translator.py — 把 LangGraph 节点完成事件翻译成前端 UI 事件
B 核心产出物

run(on_event=...) 每次只吐 (节点名, 该节点的增量dict)，这里翻译成
D 的 appStore.ts 真正需要的三种带 type 事件：log / node_status / progress；
另外 _on_validator 每轮还会额外吐一条无 type 字段的扁平 Validator 结果
（{passed, logs, screenshot, failed_tests, iteration}），前端
agentClient.ts 的 isValidatorPayload() 专门认这个形状（problem.md 第39条）。

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
        self._frontend_runs = 0
        self._frontend_done = False
        self._max_progress = 0
        self._validator_runs = 0

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
            raise RuntimeError(f"未实现 LangGraph 节点事件翻译: {node_name}")
        return handler(output)

    def _on_decompose(self, output: dict) -> list[dict]:
        decomp = output.get("task_decomposition")
        if decomp is None:
            raise RuntimeError("Commander 节点没有回传 task_decomposition")
        app_name = getattr(decomp, "app_name", None) or "未命名"
        n_tasks = len(getattr(decomp, "tasks", None) or [])
        if n_tasks == 0:
            raise RuntimeError("Commander 没有拆出任何子任务")
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
        # backend_generated=False：本轮 LLM 输出没通过校验（比如漏实现某个接口
        # 函数），backend_expert_node 已经老实返回失败信号而不是 raise（跟
        # test_expert_node 的"不直接raise"原则一致），这里同样不能再拿"必须有
        # path/code"的老标准去拦这个合法的失败结果
        if output.get("backend_generated") is False:
            events.append(self._log("BackendExpert", "本轮后端代码生成失败，保留上一轮代码，等待下一轮重试", "warn"))
            events.append(self._status("backend", "error"))
            return events
        path = output.get("backend_path")
        if not path or not output.get("backend_code"):
            raise RuntimeError("BackendExpert 事件缺少 backend_path/backend_code，不能视为生成完成")
        events.append(self._log("BackendExpert", f"后端代码生成完成: {path}", "success"))
        events.append(self._status("backend", "success"))
        if self._frontend_done:
            events.append(self._status("test", "running"))
        return events

    def _on_frontend_expert(self, output: dict) -> list[dict]:
        self._frontend_runs += 1
        self._frontend_done = True
        events = []
        if self._frontend_runs > 1:
            events.append(self._log("System", f"第 {self._frontend_runs - 1} 轮修复（前端）开始", "warn"))
        # frontend_generated=False：本轮 LLM 输出没通过校验（比如生成的代码
        # 不是 Tkinter 应用），frontend_expert_node 已经老实返回失败信号而不是
        # raise（跟 test_expert_node 的"不直接raise"原则一致），这里同样不能
        # 再拿"必须有 path/code"的老标准去拦这个合法的失败结果——这条分支在
        # frontend_expert 只跑一次的年代走不到，现在它会在重试轮次里被反复
        # 调用，必须能优雅处理
        if output.get("frontend_generated") is False:
            events.append(self._log("FrontendExpert", "本轮界面代码生成失败，保留上一轮代码，等待下一轮重试", "warn"))
            events.append(self._status("frontend", "error"))
            if self._backend_runs >= 1:
                events.append(self._status("test", "running"))
            events.append(self._progress(45))
            return events
        path = output.get("frontend_path")
        if not path or not output.get("frontend_code"):
            raise RuntimeError("FrontendExpert 事件缺少 frontend_path/frontend_code，不能视为生成完成")
        events.append(self._log("FrontendExpert", f"前端代码生成完成: {path}", "success"))
        events.append(self._status("frontend", "success"))
        if self._backend_runs >= 1:
            events.append(self._status("test", "running"))
        events.append(self._progress(45))
        return events

    def _on_test_expert(self, output: dict) -> list[dict]:
        passed = output.get("test_passed")
        path = output.get("test_path")
        if passed is None:
            raise RuntimeError("TestExpert 事件缺少 test_passed")
        # 不要求 path/test_code 一定非空——backend_code 为空这类可重试的失败，
        # test_expert_node 会老实返回 test_passed=False + path/test_code=None，
        # 这是合法的"没通过"结果，不是事件格式错误，不该在这里被当成畸形事件拦下来
        level = "success" if passed else "warn"
        events = [
            self._log("TestExpert", f"测试{'通过' if passed else '失败'}: {path or '(未生成)'}", level),
            self._status("test", "success" if passed else "error"),
            self._status("validator", "running"),
        ]
        events.append(self._progress(75))
        return events

    def _on_validator(self, output: dict) -> list[dict]:
        self._validator_runs += 1
        passed = output.get("validation_passed")
        logs = output.get("validation_logs") or []
        if passed is None:
            raise RuntimeError("Validator 事件缺少 validation_passed")
        events = [self._log("Validator", str(line), "info") for line in logs]
        if passed:
            events.append(self._log("Validator", "验证通过", "success"))
            events.append(self._status("validator", "success"))
            events.append(self._progress(100))
        else:
            events.append(self._log("Validator", "验证未通过，准备重试", "warn"))
            events.append(self._status("validator", "error"))
        # 逐轮把 Validator 原始结果（passed/screenshot/failed_tests/iteration）推给
        # 前端——之前只有整个流程结束时 run.py 的 done 事件带这几个字段，中途每一轮
        # 验证的截图/失败用例/轮次前端全程看不到（problem.md 第39条）。这里复用
        # agentClient.ts 已经写好的 isValidatorPayload()/applyValidatorResult()——
        # 它只认"无 type 字段但有布尔 passed"这个形状，不关心是中途推的还是
        # done 里带的，不需要改前端代码
        events.append({
            "passed": bool(passed),
            "logs": logs,
            "screenshot": output.get("screenshot_path") or "",
            "failed_tests": output.get("failed_tests") or [],
            "iteration": self._validator_runs,
        })
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
