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
5. **这只是 `api_spec.functions` 这一段的格式，不是完整输出**：最终必须输出的顶层
   JSON 结构（`app_name`/`api_spec`/`tasks`/`estimated_iterations`）以调用方 System
   Prompt 里"输出格式"那节为准，下面只演示 `functions` 内部长什么样——不要只输出
   这一小段就当作完整答案

## `api_spec.functions` 内部格式示例（只是片段，不是完整输出）
```json
{
  "create_todo": {"params": [{"name": "title", "type": "str"}], "return": "int"},
  "get_all_todos": {"params": [], "return": "List[dict]"},
  "delete_todo": {"params": [{"name": "todo_id", "type": "int"}], "return": "bool"}
}
```
