# 开发进度 · 多角色 Agent 协作平台

> 实训项目 #21 · 大模型方向
> 更新日期：2026-07-01

---

## 里程碑总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| M1 环境搭建 | Ollama + Python venv + FastAPI 骨架 | ✅ 完成 |
| M2 核心链路 | Commander（A）→ Expert（B）→ Validator（C）主链路 | 🔄 A 已完成，等 B/C |
| M3 功能完善 | Validator闭环 + MCP + Skills 集成 | ⏳ |
| M4 前端可视化 | Web控制台 + 实时日志 + DAG图 | ⏳ |
| M5 演示交付 | Docker打包 + 演示录制 + 文档 | ⏳ |

---

## 进度明细

### ✅ 已完成

| 模块 | 完成项 | 负责人 | 日期 |
|------|--------|--------|------|
| **架构设计** | 技术栈评审（LangGraph / pywinauto / ChromaDB 取代原方案） | 全员 | 06-30 |
| **架构设计** | 接口优先设计确定（Commander 先生成 api_spec 再分配任务） | 全员 | 06-30 |
| **架构设计** | 分工表确定 + 接口格式统一 | 全员 | 06-30 |
| **A-Commander** | Ollama 部署，Qwen2.5-Coder:7B(4.7GB) + 1.5B(986MB) 已拉取 | A | 07-01 |
| **A-Commander** | `ollama_client.py` — requests 直连 Ollama API，稳定调用 | A | 07-01 |
| **A-Commander** | `schemas.py` — Pydantic 模型定义（TaskDecomposition / SubTask / ApiSpec） | A | 07-01 |
| **A-Commander** | `commander_prompt.py` — 接口优先设计 System Prompt | A | 07-01 |
| **A-Commander** | `decompose.py` — 核心拆解逻辑，7B→1.5B→兜底 三级降级 | A | 07-01 |
| **A-Commander** | `call_log.py` — 调用记录（耗时+Token 存 SQLite） | A | 07-01 |
| **A-Commander** | **端到端验证通过** — 7B 模型正常拆解需求，输出格式正确 | A | 07-01 |
| **A-Commander** | `agent-A.md` + `progress.md` 维护 | A | 07-01 |
| **项目仓库** | 仓库 `agentforge` 初始化 + CLAUDE.md | 组员 | 07-01 |
| **项目仓库** | 架构设计文档（HTML 页面） | 组员 | 07-01 |

### 🔄 进行中

| 模块 | 当前任务 | 负责人 | 备注 |
|------|---------|--------|------|
| A-Commander | 等待 B 联调 decompose() 集成 | A | 接口已就绪，随时可调 |

### ⏳ 待开始

| 模块 | 任务 | 负责人 |
|------|------|--------|
| B-流程控制 | LangGraph StateGraph 骨架 + 专家Agent Prompt + MCP 集成 | B |
| C-验证测试 | 验证者 Agent Prompt + ruff 检查 + pywinauto 桌面控制 | C |
| D-前端 | React 搭建 + WebSocket + DAG 可视化 + 指标面板 | D |
| 联调 | A→B→C 全链路端到端测试 | 全员 |
| 部署 | Docker Compose 一键启动 | 全员 |
| 演示 | 演示场景调试 + 录制 | 全员 |

---

## 接口约定（定死不改）

### 接口1：A → B（需求 → 任务清单）

```python
from backend.agents.commander import decompose
result = decompose("做一个待办事项应用")
# result.tasks → [SubTask, ...]
# result.api_spec.functions → {函数名: {params, return}}
```

### 接口2：B → C（代码路径 → 测试报告）
```json
输入：{"app_path": "./output/xxx/main.py"}
输出：{"passed": true, "logs": [...], "screenshot": "base64..."}
```

### 接口3：所有人 → D（进度推送）
```json
{"step": "代码生成中...", "progress": 60, "agent": "BackendExpert"}
```

---

## 风险跟踪

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| 本地 7B 推理慢（~10-30s/次） | 高 | 中 | 限制 max_tokens=2048 |
| Agent 无限循环 | 中 | 高 | iteration_count 超 5 轮强制终止 |
| 桌面自动化不稳定 | 中 | 中 | 演示优先 Web 应用（Playwright），桌面控制作加分项 |
| LangGraph 学习曲线 | 中 | 中 | 先跑通 StateGraph Hello World |
| ~~langchain-ollama 兼容性差~~ | ✅ 已解决 | — | 改用 requests 直连更稳定 |
