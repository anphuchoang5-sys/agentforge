# 开发进度 · 多角色 Agent 协作平台

> 实训项目 #21 · 大模型方向
> 更新日期：2026-07-03

---

## 里程碑总览

| 阶段 | 目标 | 状态 |
|------|------|------|
| M1 环境搭建 | DeepSeek API 接入 + Python venv + 项目骨架 | ✅ 完成 |
| M2 核心链路 | Commander（A）→ Expert（B）→ Validator（C）主链路 | 🔄 A/B 已完成，等 C |
| M3 功能完善 | Validator 闭环 + MCP + Skills 集成 | 🔄 MCP/Skills 已完成，闭环等 C 真实实现 |
| M4 前端可视化 | Web 控制台 + 实时日志 + DAG 图 | ⏳ |
| M5 演示交付 | Docker 打包 + 演示录制 + 文档 | ⏳ |

---

## 进度明细

### ✅ 已完成

| 模块 | 完成项 | 负责人 | 日期 |
|------|--------|--------|------|
| **架构设计** | 技术栈评审（LangGraph / pywinauto / ChromaDB 取代原方案） | 全员 | 06-30 |
| **架构设计** | 接口优先设计确定（Commander 先生成 api_spec 再分配任务） | 全员 | 06-30 |
| **架构设计** | 分工表确定 + 接口格式统一（定后不改） | 全员 | 06-30 |
| **A-Commander** | `schemas.py` — Pydantic 模型（TaskDecomposition / SubTask / ApiSpec，含 app_name 字段） | A | 07-01 |
| **A-Commander** | `commander_prompt.py` — 接口优先设计 System Prompt | A | 07-01 |
| **A-Commander** | `decompose.py` — 需求拆解逻辑，失败即报错，不用硬编码兜底 | A | 07-02 |
| **A-Commander** | `call_log.py` — 调用记录（耗时+Token 存 SQLite，供 D 展示） | A | 07-01 |
| **A-Commander** | `ollama_client.py` 切换为 DeepSeek API 优先，Ollama 仅离线兜底 | A | 07-02 |
| **B-流程控制** | `graph/project_state.py` — ProjectState 白板定义 | B | 07-02 |
| **B-流程控制** | `graph/workflow.py` — LangGraph StateGraph，含重试闭环 + 汇合边 bug 排查 | B | 07-02 |
| **B-流程控制** | `agents/experts/` — BackendExpert / FrontendExpert / TestExpert，通用命名不绑定具体应用 | B | 07-02 |
| **B-流程控制** | `agents/experts/output_naming.py` — 应用名解析（Commander app_name 优先，函数名派生兜底） | B | 07-02 |
| **B-流程控制** | `agents/validator_stub.py` — C 的接口桩，`.env` 加 `VALIDATOR_URL` 后可无缝切换真实服务 | B | 07-02 |
| **B-流程控制** | `tools/` — write_file / read_file / run_command | B | 07-02 |
| **B-流程控制** | `mcp_tools/mcp_server.py` — FastMCP 包装文件与命令工具 | B | 07-02 |
| **B-流程控制** | `pipeline/run.py` — run(user_input) 全流程唯一入口 | B | 07-02 |
| **B-流程控制** | `skills/` — build/test/spec 三个 SKILL.md | B | 07-02 |
| **B-流程控制** | **端到端验证通过** — 真实需求跑通全流程，含真实触发的失败重试闭环（3 轮后通过） | B | 07-03 |
| **B-流程控制** | 生成代码用 ruff 抽查，无语法错误/无 SQL 注入，仅风格级问题 | B | 07-03 |
| **B-流程控制** | 生成的 Tkinter 应用用 PyInstaller 打包成 exe 验证可行性（未纳入正式流水线） | B | 07-03 |
| **项目仓库** | 仓库 `agentforge` 初始化 + CLAUDE.md | 组员 | 07-01 |
| **项目仓库** | 架构设计文档（HTML 页面） | 组员 | 07-01 |

| D-前端 | Vite + React + TypeScript 项目初始化 | D | 07-02 |
| D-前端 | TailwindCSS + shadcn/ui 组件库配置 | D | 07-02 |
| D-前端 | Zustand 全局状态管理（进度/日志/节点状态） | D | 07-03 |
| D-前端 | Mock WebSocket 模拟 Agent 执行流程（接口优先顺序） | D | 07-03 |
| D-前端 | Agent 流程图节点状态展示（6个角色，蓝/绿/灰状态） | D | 07-03 |
| D-前端 | 实时终端日志（xterm风格，自动滚动） | D | 07-03 |
| D-前端 | Token 消耗柱状图（Recharts） | D | 07-03 |
| D-前端 | 前端代码已推送至 Gitee | D | 07-03 |
| D-前端 | 适配 Validator 接口格式（截图/日志颜色/迭代轮次/failed_tests） | D | 07-04 |
| D-前端 | 前端界面已就绪，等待后端 WebSocket 真实对接 | D | 07-04 |

### 🔄 进行中

| 模块 | 当前任务 | 负责人 | 备注 |
|------|---------|--------|------|
| C-验证测试 | 验证者 Agent 待实现，真实替换 `validator_stub.py` 里的 Mock | C | 接口③已锁定，B 侧接入点已就绪，`.env` 加 `VALIDATOR_URL` 即可切换 |

### ⏳ 待开始

| 模块 | 任务 | 负责人 |
|------|------|--------|
| C-验证测试 | 验证者 Agent Prompt + ruff 检查 + pywinauto 桌面控制 | C |

| D-前端 | 对接真实 WebSocket（等待 B 提供接口地址） | D |
| 联调 | A→B→C 全链路端到端测试（接入 C 的真实验证服务） | 全员 |
| 部署 | Docker Compose 一键启动 | 全员 |
| 演示 | 演示场景调试 + 录制 | 全员 |

---

## 接口约定（定死不改，对齐最终分工表）

### 接口1：A 对外提供（用户需求 → 任务清单）
```python
from backend.agents.commander import decompose
result = decompose("做一个待办事项应用")
# result.app_name              → 应用名（可能为 None）
# result.api_spec.functions    → {函数名: {params, return}}
# result.tasks                 → [SubTask, ...]
```

### 接口2：B 对外提供（用户需求 → 代码落地 → 测试报告）
```python
from backend.pipeline.run import run
result = run("帮我做一个待办事项桌面应用")
# {"deliverable": "./output/xxx.zip", "app_path": "...", "test_report": {...}}
```

### 接口3：C 对外提供（代码路径 → 测试报告，B 调用方）
```json
输入：{"app_path": "./output/xxx/app.py"}
输出：{"passed": true, "logs": [...], "screenshot": "base64...", "failed_tests": []}
```
现状：`backend/agents/validator_stub.py` 走本地 Mock 占位，`.env` 加 `VALIDATOR_URL` 后自动切真实调用。

### 接口4：所有人 → D（进度推送）
```json
{"step": "代码生成中...", "progress": 60, "agent": "BackendExpert"}
```
现状：尚未接入，D 侧仍需用 Mock 数据独立开发。

---

## 风险跟踪

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| Agent 无限循环 | 中 | 高 | iteration_count 超 5 轮强制终止（已验证：真实触发过 3 轮重试后正常收敛） |
| 桌面自动化不稳定 | 中 | 中 | 演示优先 Web 应用（Playwright），桌面控制作加分项 |
| C 的验证逻辑迟迟不上线 | 中 | 中 | B 已用 Mock 桩解耦，不阻塞主链路联调 |
| D 前端进度推送未接入 | 中 | 低 | D 独立用 Mock 数据开发，不阻塞 B 主链路 |
| LLM 生成代码含 lint 级问题（未用变量/== True 比较等） | 低 | 低 | 不影响功能，已用 ruff 抽查确认无真实 bug；是否引入 ruff 自动修复关卡待评估 |
| ~~本地 7B 推理慢（~10-30s/次）~~ | ✅ 已解决 | — | 已切换 DeepSeek API 为主力 |
| ~~langchain-ollama 兼容性差~~ | ✅ 已解决 | — | 改用 requests 直连更稳定 |


