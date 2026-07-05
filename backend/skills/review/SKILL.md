---
name: review
description: 代码审查技能 — 逐条核对验收标准 + 静态检查，不让代码带着已知问题过关
level: L2
agents: [Validator]
---

# /review 技能

## 激活时机
BackendExpert/FrontendExpert/TestExpert 产出代码后，Validator 独立介入审计，
不信任专家 Agent 自我报告的"已完成"。

## 执行规则
1. **两条腿走路**：ruff 静态检查（语法错误/未使用变量等结构性问题）+ LLM 逐条核对
   acceptance_criteria（语义/功能性是否真的实现），两者互补，不能只做一种
2. **证据优先**：判断某条验收标准是否实现时，必须引用具体函数名/行号作为证据，
   不能只给"通过"/"不通过"的结论
3. **区分严重程度**：verdict 分 passed/failed/partial，severity 分 error（阻断性，
   影响最终 passed 判定）和 warning（提示性，不影响判定）——避免过度苛刻的标准
   （比如"窗口不可调整大小"）把功能上没问题的代码错误打回重做
4. **只读不改**：Validator 只判断，不直接修改代码——判定失败后交给 workflow.py
   的条件边触发对应专家 Agent 重新生成，职责分离

## 输出格式
```json
{
  "results": [
    {"criteria": "支持添加任务", "verdict": "passed", "evidence": "create_todo() 第15行", "severity": "error"}
  ],
  "all_passed": false,
  "summary": "..."
}
```

## 质量检查点
- [ ] verdict 只能是 passed/failed/partial（partial 按 failed 处理）
- [ ] 每条 evidence 引用具体代码位置，不写"看起来实现了"这种模糊描述
- [ ] ruff 检查和 LLM 核对的结果都体现在最终判定里，不能只看一边就下结论
