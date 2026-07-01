# Agent A · 需求理解与拆解（Commander）

> 对齐文档：`CLAUDE.md`（团队架构）+ `指挥官层.html`（最新设计）+ `最终分工表`（团队约定）

## 角色定位

我是**同学A**，负责**指挥官层（Commander）**。

核心职责：让AI听懂人话，把一句话需求拆成**接口规范 + 任务清单**。
采用**接口优先设计**——先定函数签名（谁调谁），再让 Backend / Frontend / Test 并行开发。

---

## 我的代码

```
agentforge/
└── backend/agents/commander/
    ├── __init__.py           # 导出 decompose() / health_check()
    ├── ollama_client.py      # requests 调 Ollama API（比 langchain-ollama 更稳定）
    ├── schemas.py            # Pydantic 模型（TaskDecomposition / SubTask / ApiSpec）
    ├── commander_prompt.py   # System Prompt（接口优先设计）
    ├── decompose.py          # 核心拆解逻辑（7B→1.5B→兜底 三级降级）
    └── call_log.py           # 调用记录（耗时+Token 存 SQLite 供 D 展示）
```

---

## 对外接口

```python
# B 调这一行就够了
from backend.agents.commander import decompose

result = decompose("做一个待办事项应用")

result.api_spec.functions   # 接口规范：{函数名: {params, return}}
result.tasks                # 任务清单：[SubTask(...), ...]
result.estimated_iterations # 预估修复轮数
```

---

## 输出格式（Pydantic 结构化，定死不改）

```json
{
  "api_spec": {
    "functions": {
      "create_todo": {
        "params": [{"name": "title", "type": "str"}],
        "return": "int"
      },
      "get_all_todos": {
        "params": [],
        "return": "List[dict]"
      }
    }
  },
  "tasks": [
    {"id": "task_1", "type": "backend",     "description": "实现SQLite数据库", "dependencies": [],        "acceptance_criteria": ["数据库文件创建成功"]},
    {"id": "task_2", "type": "frontend",    "description": "用Tkinter写界面",  "dependencies": [],        "acceptance_criteria": ["界面可显示任务列表"]},
    {"id": "task_3", "type": "test",        "description": "写pytest测试",     "dependencies": [],        "acceptance_criteria": ["测试全部通过"]},
    {"id": "task_4", "type": "ui_validate", "description": "截图验证UI",       "dependencies": ["task_2"], "acceptance_criteria": ["截图包含按钮和列表"]}
  ],
  "estimated_iterations": 1
}
```

**关键设计**：backend / frontend / test 三者并行（dependencies为空），只有 ui_validate 依赖 frontend 完成后才执行。

---

## 工作项完成情况

| 工作项（对齐分工表） | 状态 | 文件 |
|--------|------|------|
| Ollama 部署 + 拉模型 | ✅ 7B(4.7GB) + 1.5B(986MB) | `ollama pull Qwen2.5-Coder:7B` |
| API 封装（requests 直连） | ✅ 已调通 | `ollama_client.py` |
| System Prompt（接口优先） | ✅ 已写 | `commander_prompt.py` |
| 需求拆解逻辑 | ✅ 7B 正常拆解 | `decompose.py` |
| Pydantic 数据模型 | ✅ 已定义 | `schemas.py` |
| 异常处理（三级降级） | ✅ 7B→1.5B→兜底 | `decompose.py` |
| 调用记录（耗时+Token） | ✅ 已写 | `call_log.py` |
| 端到端验证 | ✅ 7B 跑通，输出格式正确 | `python decompose.py` |

---

## 依赖关系

| 我依赖谁 | 内容 |
|---------|------|
| **Ollama（本地）** | Qwen2.5-Coder:7B（主用）/ 1.5B（降级） |

| 谁依赖我 | 内容 |
|---------|------|
| **B（流程控制）** | 调 `decompose()` 拿任务清单 + 接口规范 |
| **D（前端）** | 通过 `call_log.py` 读取 Token 消耗和耗时数据展示图表 |

---

## 本地运行方式

```bash
cd agentforge/backend/agents/commander

# 安装依赖
pip install requests pydantic

# 跑测试
python decompose.py
```
