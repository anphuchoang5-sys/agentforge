---
name: plan
description: 任务规划技能 — 把接口规范拆解成可并行执行的原子任务，标注依赖关系
level: L2
agents: [Commander]
---

# /plan 技能

## 激活时机
Commander 完成 spec（接口规范）之后，第二步把功能拆解成任务清单。

## 执行规则
1. **先 spec 后 plan**：必须已有 api_spec 才能分配任务，不凭空拆任务
2. **按角色分类**：每个任务的 type 只能是 backend/frontend/test/ui_validate 之一
3. **标注依赖**：test 依赖 backend，ui_validate 依赖 frontend，backend/frontend 互不依赖，可并行
4. **每种角色最多一条任务**：当前下游三个专家 Agent 只读同类型任务列表里的第一条，
   同一种 type 拆出多条任务，后面的会被静默丢弃（problem.md 第35条），拆分任务时不要
   把同一角色的工作拆成两条并列任务，要合并成一条更完整的描述
5. **验收标准要可验证**：每条 acceptance_criteria 必须是能在代码里找到具体证据的描述，
   不要写"体验良好""界面美观"这种无法核对的标准

## 输出格式
```json
{
  "tasks": [
    {"id": "task_1", "type": "backend", "description": "...", "dependencies": [], "acceptance_criteria": ["..."]},
    {"id": "task_2", "type": "frontend", "description": "...", "dependencies": [], "acceptance_criteria": ["..."]},
    {"id": "task_3", "type": "test", "description": "...", "dependencies": ["task_1"], "acceptance_criteria": ["..."]},
    {"id": "task_4", "type": "ui_validate", "description": "...", "dependencies": ["task_2"], "acceptance_criteria": ["..."]}
  ]
}
```

## 质量检查点
- [ ] 每个任务的 dependencies 只引用已存在的 task id
- [ ] backend/frontend/test/ui_validate 各自最多一条任务
- [ ] acceptance_criteria 逐条可在代码里核对，不写模糊描述
