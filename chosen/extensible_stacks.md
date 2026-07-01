# 可拓展的其他技术栈

> 本文档列出当前选型之外、可在项目迭代或升级时引入的技术选项。
> 状态：待审定（需求分析阶段）
> 更新日期：2026-06-30

---

## 1. Agent 编排框架备选

| 框架 | GitHub | Stars | 适用场景 |
|------|--------|-------|---------|
| **AutoGen 0.4+** | microsoft/autogen | 38k+ | 对话驱动多 Agent，微软生态；比 LangGraph 更适合开放式对话 |
| **Semantic Kernel** | microsoft/semantic-kernel | 22k+ | 企业级，.NET/Python 双语言，微软 Copilot 底层 |
| **LlamaIndex Workflows** | run-llama/llama_index | 36k+ | RAG 场景强，工作流支持有限 |
| **DSPy** | stanfordnlp/dspy | 22k+ | 自动优化 Prompt，学术场景；无工作流调度 |
| **Haystack** | deepset-ai/haystack | 18k+ | 企业 NLP 流水线，偏 RAG；Agent 支持弱于 LangGraph |

**升级时机**：若需要多 Agent P2P 直接通信（不经指挥官中转）→ 考虑 AutoGen；若需要 .NET 后端 → 考虑 Semantic Kernel

---

## 2. LLM 模型升级路径

| 阶段 | 模型 | 说明 |
|------|------|------|
| 当前（MVP） | Qwen2.5-Coder:7b / 14b | 本地 Ollama，8GB 显存可跑 |
| 升级 1 | DeepSeek-Coder-V2:16b | 代码能力更强，需 16GB 显存 |
| 升级 2 | Claude claude-haiku-4-5 API | Commander 用云端 API，速度快 |
| 升级 3 | 异构模型路由 | 推理用 Claude + 代码用 DeepSeek + 测试用 GPT-5.4 |
| 长期 | 私有化部署云端 LLM | 从单机扩展到云端推理层 + 本地执行层协同 |

**多模型路由参考**：
- **LiteLLM**: https://github.com/BerriAI/litellm ⭐15k+ — 统一多 LLM 接口，一行切换模型

---

## 3. 向量数据库升级路径

| 阶段 | 选型 | GitHub | 说明 |
|------|------|--------|------|
| 当前（MVP） | ChromaDB | chroma-core/chroma ⭐17k+ | 零配置，本地文件 |
| 升级 1 | Qdrant | qdrant/qdrant ⭐21k+ | 高性能，Docker 部署，支持过滤 |
| 升级 2 | Milvus | milvus-io/milvus ⭐31k+ | 生产级，支持亿级向量；需 K8s |
| 升级 3 | Weaviate | weaviate/weaviate ⭐11k+ | 原生多模态，GraphQL 查询 |

---

## 4. 消息队列升级路径

| 阶段 | 选型 | 说明 |
|------|------|------|
| 当前（MVP） | asyncio.Queue | 单机，无需部署 |
| 升级 1 | Celery + Redis | 支持分布式任务，持久化队列 |
| 升级 2 | Kafka | 高吞吐，支持多消费者；过重 |
| 升级 3 | Dapr | 原题建议，微服务编排；引入复杂度高 |

---

## 5. 前端升级路径

| 当前 | 备选 | 说明 |
|------|------|------|
| React 18 | **Next.js 15** | SSR + App Router，SEO 支持；演示项目不需要 |
| React 18 | **Vue 3 + Vite** | 原题也建议 Vue，学习曲线更低 |
| shadcn/ui | **Ant Design Pro** | 企业级，开箱即用的 Dashboard |
| React Flow | **D3.js** | 完全自定义 Agent 图，学习成本高 |
| Recharts | **ECharts** | 百度出品，图表类型更丰富 |

---

## 6. 桌面控制升级路径

| 工具 | GitHub | 场景 | 优先级 |
|------|--------|------|--------|
| pywinauto（当前） | pywinauto/pywinauto ⭐4k+ | Windows 原生 GUI | 首选 |
| OpenClaw（当前） | openclaw/openclaw ⭐380k+ | 跨应用 AI Agent | 首选（跨平台） |
| Playwright（当前） | microsoft/playwright ⭐67k+ | Web 应用 UI 测试 | 演示首选 |
| **PyAutoGUI**（降级） | asweigart/pyautogui ⭐11k+ | 截图存档 | 仅截图 |
| **agent-aid** | — | Win32 Accessibility 轻封装 | 可选 |
| **Appium** | appium/appium ⭐18k+ | 移动端 + 跨平台 | 超出 2 周范围 |

---

## 7. 可观测性升级路径

| 层级 | 工具 | GitHub | 说明 |
|------|------|--------|------|
| 当前 | Jaeger | jaegertracing/jaeger ⭐20k+ | 分布式追踪，Docker 一键 |
| 当前 | LangSmith | SaaS | LLM 调用专项 |
| 升级 1 | Grafana + Tempo | grafana/grafana ⭐64k+ | 替换 Jaeger，更强的指标+追踪集成 |
| 升级 2 | Grafana + Prometheus | — | 加入系统指标监控（CPU/显存/响应时间） |
| 升级 3 | Datadog / New Relic | SaaS | 企业级，超出演示需求 |

---

## 8. 记忆管理升级路径

| 阶段 | 选型 | 说明 |
|------|------|------|
| Week 1 | LangGraph MemorySaver | 会话内记忆，内置，零配置 |
| Week 2 | mem0 + ChromaDB | 跨会话记忆，向量检索 |
| 后续 | 自定义 RAG 系统 | 检索特定领域知识库 |
| 后续 | Zep | getzep/zep ⭐2k+ — 专为 LLM 会话记忆设计 |

---

## 9. 部署升级路径

| 阶段 | 方案 | 说明 |
|------|------|------|
| 当前 | Docker Compose | 单机全栈，`docker-compose up` |
| 升级 1 | Kubernetes | 多副本，生产级；超出 2 周范围 |
| 升级 2 | Dapr on K8s | 微服务编排 + 服务网格 |
| 升级 3 | 云端推理 + 本地执行 | 云端 LLM + 本地桌面控制协同 |

---

## 10. 安全与治理（生产化必要扩展）

| 能力 | 工具 | 说明 |
|------|------|------|
| 代码沙箱 | **E2B** | e2b-dev/e2b ⭐7k+ — 隔离执行 Agent 生成的代码 |
| Agent 防护 | **LLM Guard** | protectai/llm-guard ⭐4k+ — 输入输出安全过滤 |
| 权限控制 | FastAPI + OAuth2 | 多用户场景必须 |
| 审计日志 | OpenTelemetry | 所有 Agent 调用留存 |

---

## 11. 未来架构演进

### P2P Agent 通信矩阵
当专家 Agent 需要直接协商（不经指挥官中转）时：
- 参考 **AutoGen 0.4+** 的 `Group Chat` 模式
- 或引入 A2A（Agent-to-Agent）协议（Google 2026 年提出的标准草案）

### GPT-5.4 级别推理 Agent
- 将 Commander 从本地 14B 模型升级至云端推理层（Claude claude-opus-4-8 或 GPT-5.4）
- 本地 Expert Agent 保留，处理低延迟代码生成
- 参考 Microsoft Agent Framework v1.0 原生 MCP/A2A/OpenAPI 支持

### 多厂牌模型协作
```python
# 异构模型路由示例（通过 LiteLLM）
commander_llm = ChatAnthropic(model="claude-opus-4-8")  # 推理
expert_llm = ChatOllama(model="qwen2.5-coder:7b")      # 代码
test_llm = ChatOpenAI(model="gpt-5.4")                  # 测试
```
