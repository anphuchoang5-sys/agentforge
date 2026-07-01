# 技术栈选型合理性分析

> 状态：待审定（需求分析阶段）
> 更新日期：2026-06-30

## 选型原则

1. **演示可靠性优先** — 2 周内能稳定跑出完整演示 > 功能完整但不稳定
2. **学习成本控制** — 选生态成熟、文档齐全的库，避免过深的学习曲线
3. **本地优先** — 减少外部依赖，Ollama + SQLite + ChromaDB 均可本地运行
4. **可替换性** — 每个选型均有明确的替代方案，见 extensible_stacks.md

---

## 1. Agent 编排框架

### ✅ LangGraph
- **GitHub**: https://github.com/langchain-ai/langgraph ⭐20k+
- **选择理由**:
  - 有向图 + 条件边，原生支持"写代码→验证→修复"循环
  - `MemorySaver` 内置断点续跑，不需要手动管理状态
  - 生态最成熟，文档完善，2026 年 Agent 编排事实标准
  - `LangGraph Streaming` 支持逐 token 流式推送到前端，演示体验关键
- **替代了什么**: 原题 Microsoft Agent Framework（命名模糊，可能指 AutoGen/Semantic Kernel）/ CAMEL（学术框架，无条件边）

---

## 2. 前端

### ✅ React 18 + TypeScript
- **GitHub**: https://github.com/facebook/react ⭐230k+
- **选择理由**: 2026 年前端标配，团队熟悉度高，原题已建议

### ✅ TailwindCSS v3
- **GitHub**: https://github.com/tailwindlabs/tailwindcss ⭐84k+
- **选择理由**: 工具类 CSS，快速布局，原题已建议

### ✅ shadcn/ui
- **GitHub**: https://github.com/shadcn-ui/ui ⭐65k+
- **选择理由**: 基于 Radix UI，无样式侵入，演示效果好，比 Ant Design/MUI 更现代

### ✅ @xyflow/react（React Flow）
- **GitHub**: https://github.com/xyflow/xyflow ⭐27k+
- **选择理由**: 可拖拽节点图，专门用于展示 Agent 协作链路（节点=Agent，边=数据流）

### ✅ Zustand
- **GitHub**: https://github.com/pmndrs/zustand ⭐50k+
- **选择理由**: 轻量状态管理，WebSocket 实时状态更新场景下比 Redux 更简单

### ✅ xterm.js
- **GitHub**: https://github.com/xtermjs/xterm.js ⭐17k+
- **选择理由**: 模拟终端 UI，显示 Agent 流式输出，演示效果佳

### ✅ Recharts
- **GitHub**: https://github.com/recharts/recharts ⭐24k+
- **选择理由**: Token 用量/执行时间可视化，基于 D3，React 集成好

### ✅ cmdk
- **GitHub**: https://github.com/pacocoursey/cmdk ⭐10k+
- **选择理由**: 命令面板，快速输入需求，演示交互体验好

---

## 3. 后端 API 层

### ✅ FastAPI
- **GitHub**: https://github.com/fastapi/fastapi ⭐80k+
- **选择理由**: 原生异步，WebSocket 支持好，Pydantic 集成，自动生成 API 文档

### ✅ Pydantic v2
- **GitHub**: https://github.com/pydantic/pydantic ⭐22k+
- **选择理由**: Agent 结构化输出必备，FastAPI 内置，比 v1 快 5-50x，Rust 实现

### ✅ SQLAlchemy
- **GitHub**: https://github.com/sqlalchemy/sqlalchemy ⭐9k+
- **选择理由**: ORM 任务持久化，支持 SQLite，2 周项目足够

### ✅ asyncio.Queue（任务调度）
- **选择理由**: 单机项目无需引入 Celery/Redis/Dapr，asyncio 原生即可
- **替代了什么**: 原题 Dapr（分布式基础设施，2 周配置成本过高）

---

## 4. 本地 LLM

### ✅ Ollama
- **GitHub**: https://github.com/ollama/ollama ⭐100k+
- **选择理由**: 本地 LLM 运行时标准，一行命令启动，原题已建议

### ✅ Qwen2.5-Coder:7b（Expert Agent）/ Qwen2.5:14b（Commander）
- **选择理由**:
  - 中文友好，代码生成能力强
  - 7B 在 8GB 显存可跑（实际占用约 6GB）
  - Commander 需要更强推理，用 14B；代码生成用 7B 够用
  - 备选：`qwen2.5-coder:3b`（显存不足时）或 Claude Haiku API（Commander 加速）

---

## 5. Agent Skills 层

### ✅ google-gemini/agent-skills（参考）
- **GitHub**: https://github.com/google-gemini/agent-skills ⭐18k+
- **使用方式**: 参考其三层渐进式加载机制（L1发现/L2激活/L3穿透）**自研** Skill 层
- **注意**: 不能直接 pip install，需参考 SKILL.md 结构手动集成 6 个阶段（spec/plan/build/test/review/ship）

---

## 6. 记忆管理

### ✅ mem0ai/mem0
- **GitHub**: https://github.com/mem0ai/mem0 ⭐25k+
- **选择理由**: 专为 Agent 记忆设计，向量+图+结构化存储，底层可用 SQLite
- **替代了什么**: 裸 SQLite（无向量检索能力，跨会话召回困难）

### ✅ ChromaDB
- **GitHub**: https://github.com/chroma-core/chroma ⭐17k+
- **选择理由**: 纯 Python，零配置，本地文件存储，比 Milvus/Qdrant 轻 10 倍，演示够用
- **替代了什么**: 原题 Qdrant/Milvus（需独立部署，2 周项目过重）

---

## 7. MCP 工具层

### ✅ MCP Official Servers
- **GitHub**: https://github.com/modelcontextprotocol/servers ⭐12k+
- **内含**: filesystem / git / sqlite MCP Server
- **选择理由**: 标准化工具接口，Agent 可动态发现工具，与 LLM 实现完全解耦

### ✅ @playwright/mcp（Playwright MCP）
- **GitHub**: https://github.com/microsoft/playwright-mcp
- **选择理由**: Web UI 自动化通过 MCP 协议暴露给 Agent，录制-回放，CI 可用

---

## 8. 桌面控制

### ✅ pywinauto
- **GitHub**: https://github.com/pywinauto/pywinauto ⭐4k+
- **选择理由**:
  - 走 Win32 Accessibility API，不依赖屏幕坐标
  - 通过 accessibility name 定位元素，分辨率无关
  - 点击准确率 >95%（vs PyAutoGUI 的坐标猜测）

### ✅ OpenClaw
- **GitHub**: https://github.com/openclaw/openclaw ⭐380k+（2026.06 数据）
- **背景**: 2026 年 1 月发布（前身 Clawdbot/Moltbot），48小时内超 10 万 Star，目前最广泛采用的开源 AI Agent 框架之一
- **选择理由**:
  - 跨平台 AI Agent，通过环境感知 + 动态决策树实现桌面自动化
  - 多渠道接入（Slack/Telegram/微信/Discord 等）
  - 可作为 UIValidator Agent 的执行后端
- **风险**: 安全研究人员发现了若干漏洞（RCE），演示隔离环境下风险低；不建议接生产网络

### ✅ Playwright（Web 优先演示）
- **GitHub**: https://github.com/microsoft/playwright ⭐67k+
- **选择理由**: 演示场景优先生成 Web 应用，Playwright 比桌面自动化更可靠

---

## 9. 代码质量

### ✅ ruff
- **GitHub**: https://github.com/astral-sh/ruff ⭐35k+
- **选择理由**: pylint 快 10x，Rust 实现，2026 年 Python lint/format 事实标准
- **替代了什么**: pylint（速度慢，配置复杂）

---

## 10. 可观测性

### ✅ OpenTelemetry Python SDK
- **GitHub**: https://github.com/open-telemetry/opentelemetry-python ⭐3k+
- **选择理由**: 分布式追踪标准，为每个 Agent 调用生成 Span，记录 Agent 名称/Skill/LLM 调用/耗时

### ✅ Jaeger
- **GitHub**: https://github.com/jaegertracing/jaeger ⭐20k+
- **选择理由**: Docker 一键启动，可视化 Agent 调用链，清晰展示指挥官如何拆解任务

### ✅ LangSmith
- **GitHub**: https://github.com/langchain-ai/langsmith-sdk（SaaS，有免费额度）
- **选择理由**: LLM 调用专项追踪，Prompt/Response/Token 可视化，调试 Agent 行为利器

---

## 11. 参考架构（仅参考，不作主框架）

### CrewAI
- **GitHub**: https://github.com/crewAIInc/crewAI ⭐30k+
- **使用方式**: 参考其 Role/Goal/Backstory 角色定义结构设计各专家 Agent 的 Prompt

---

## 汇总对比表

| 层次 | 原题建议 | 本项目选型 | 变更说明 |
|------|---------|----------|---------|
| Agent 编排 | Microsoft Agent Framework / CAMEL | **LangGraph** | 命名模糊 / 学术框架，LangGraph 更成熟 |
| 任务队列 | Dapr（可选） | **asyncio.Queue** | 分布式队列对单机项目过重 |
| 向量数据库 | Qdrant / Milvus | **ChromaDB** | 零配置，本地运行，演示够用 |
| 桌面自动化 | OpenClaw / agent-aid | **OpenClaw + pywinauto** | 两者并用，pywinauto 负责 Win32 精确控制 |
| 记忆管理 | 裸 SQLite | **mem0 + ChromaDB** | 向量检索 + 结构化存储 |
| 代码检查 | pylint | **ruff** | 快 10x，2026 年 Python 标准 |
| LLM 接入 | Ollama + DeepSeek | **Ollama + Qwen2.5-Coder** | DeepSeek 同样可选，Qwen 中文更友好 |
| 前端图表 | 原题未指定 | **shadcn/ui + React Flow** | 演示效果最好 |
