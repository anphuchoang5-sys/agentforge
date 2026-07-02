# Backend 代码结构说明

> 同学 B 负责模块：代码生成 + 流程控制

---

## 文件树

```
backend/
│
├── pipeline/
│   └── run.py                  ★ 全流程唯一入口
│                                 run(user_input) → zip 交付物
│
├── graph/
│   ├── project_state.py        ★ 所有 Agent 共享的「大白板」
│   │                             定义每个字段由谁读、谁写
│   └── workflow.py             ★ LangGraph 状态机
│                                 把所有节点连成有向图，含重试逻辑
│
├── agents/
│   ├── commander/              【同学 A 负责，B 调用】
│   │   ├── __init__.py           导出 decompose()
│   │   ├── schemas.py            TaskDecomposition / SubTask / ApiSpec 数据模型
│   │   ├── decompose.py          需求拆解核心逻辑，对接 DeepSeek
│   │   ├── ollama_client.py      统一 LLM 客户端（DeepSeek 优先，Ollama 备用）
│   │   ├── commander_prompt.py   指挥官 System Prompt
│   │   └── call_log.py           调用日志记录
│   │
│   ├── experts/                【同学 B 负责】
│   │   ├── backend_expert.py   ★ 后端专家 Agent
│   │   │                         System Prompt「你是后端工程师」
│   │   │                         生成 SQLite 数据层代码 → db.py
│   │   ├── frontend_expert.py  ★ 前端专家 Agent
│   │   │                         System Prompt「你是前端工程师」
│   │   │                         生成 Tkinter 界面代码 → app.py
│   │   └── test_expert.py      ★ 测试专家 Agent
│   │                             读取 backend_code → 生成 pytest 测试
│   │                             真实运行 pytest，结果写入白板
│   │
│   └── validator_stub.py       ★ C 的接口桩（临时）
│                                 validate(app_path, test_results) -> dict
│                                 是同学 C 真正要实现的函数（对应接口③），
│                                 现在这里放的是占位 Mock：文件存在 + 测试无
│                                 FAILED = 通过；.env 加 VALIDATOR_URL 后
│                                 自动切换为真实调用，调用方（validator_node）
│                                 不用改一行代码
│
├── tools/                      【同学 B 负责】
│   ├── file_tools.py           ★ write_file / read_file
│   │                             Agent 生成的代码字符串 → 真实磁盘文件
│   └── command_tools.py        ★ run_command
│                                 执行 pytest / python main.py 等命令
│                                 含超时保护，防止死循环代码挂死进程
│
├── mcp_tools/
│   └── mcp_server.py           ★ MCP 工具服务
│                                 将 write_file / read_file / run_command
│                                 包装为 MCP 协议，其他 Agent 可标准化调用
│                                 启动：python -m backend.mcp_tools.mcp_server
│
└── skills/                     【Agent 操作手册，B 编写】
    ├── build/
    │   └── SKILL.md              /build 技能：代码构建规范
    │                             BackendExpert + FrontendExpert 使用
    ├── test/
    │   └── SKILL.md              /test 技能：测试生成规范
    │                             TestExpert + UIValidator 使用
    └── spec/
        └── SKILL.md              /spec 技能：接口优先设计规范
                                  Commander 使用
```

---

## 调用流程

```
用户输入
  │
  ▼
pipeline/run.py          ← B 对外暴露的唯一接口
  │  run("做一个 Todo App")
  │
  ▼
graph/workflow.py        ← LangGraph 状态机启动
  │
  ├──▶ agents/commander/decompose.py    A 的代码，拆解需求
  │         └── 写入 ProjectState["task_decomposition"]
  │
  ├──▶ agents/experts/backend_expert.py  ┐
  │         └── 写入 db.py               │ 并行
  ├──▶ agents/experts/frontend_expert.py ┘
  │         └── 写入 app.py
  │
  ├──▶ agents/experts/test_expert.py    （等 BackendExpert 完成后）
  │         └── 写入 test_app.py，运行 pytest
  │
  ▼
graph/workflow.py:validator_node       调用 agents/validator_stub.py 的 validate()
  │  validate() 是 C 要实现的函数（对应最终分工表接口③），现在是占位 Mock
  │  passed? → 打包 zip 返回
  │  failed? → 重试，最多 5 次
  ▼
output/generated_app.zip               ← 交付物
```

---

## 对外接口

**B 暴露给其他同学的调用方式：**

```python
from backend.pipeline.run import run

# 全流程入口（供 D 的前端 POST /api/submit 调用）
result = run("做一个待办事项桌面应用")
# 返回：
# {
#   "deliverable": "./output/generated_app.zip",
#   "app_path": "./output/generated_app/app.py",
#   "test_report": {
#     "backend_generated": True,
#     "frontend_generated": True,
#     "iterations": 1,
#     "validation_passed": True
#   }
# }
```

**等 C 上线后，只需在 `.env` 加一行：**
```
VALIDATOR_URL=http://C的服务地址:端口
```

**B 调 C 的接口（按 C 定的接口③格式给的，字段一个不多不少）：**

```python
# backend/agents/validator_stub.py::validate()
# C 上线后，B 内部会这样调用（见 validator_url 分支）：
requests.post(f"{VALIDATOR_URL}/validate", json={"app_path": app_path})
# 输入：{"app_path": "./output/todo/app.py"}
# 期望 C 返回：
# {
#   "passed": true,
#   "logs": ["启动应用成功", "点击添加按钮成功", ...],
#   "screenshot": "base64编码的截图",
#   "failed_tests": []
# }
```

C 上线前，`validate()` 走本地 Mock，返回结构与上面完全一致（`screenshot` 暂时为 `None`），保证 C 接进来那天，`validator_node`（[graph/workflow.py](graph/workflow.py)）不用改一行代码。

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| BackendExpert → TestExpert（顺序）| TestExpert 需要读 backend_code，不能并行 |
| Frontend ‖ Backend（并行）| 两者都读接口规范，不需要等对方 |
| validator_stub 用 Mock | C 还没写好，B 不能卡死等她，.env 切换零改动 |
| 重试最多 5 次 | 防止 AI 生成死循环，超限转人工 |
| MCP Server 独立进程 | 工具与 Agent 解耦，其他人不用 import 我们的代码 |
