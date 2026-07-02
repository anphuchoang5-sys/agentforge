---
name: spec
description: 需求规格技能 — 先定规格再写代码，接口优先设计
level: L2
agents: [Commander]
---

# /spec 技能

## 激活时机
Commander 收到用户需求后，第一步先生成接口规范。

## 执行规则
1. **输出 ApiSpec**：函数名、参数类型、返回值类型，Pydantic 格式
2. **命名规范**：snake_case，动词开头（create_/get_/update_/delete_）
3. **最小化接口**：只定义需求明确要求的功能，不过度设计
4. **接口规范先于任务拆解**：spec 写完才能 plan

## 输出示例
```json
{
  "functions": {
    "create_todo": {"params": [{"name": "title", "type": "str"}], "return": "int"},
    "get_all_todos": {"params": [], "return": "List[dict]"},
    "delete_todo": {"params": [{"name": "todo_id", "type": "int"}], "return": "bool"}
  }
}
```
