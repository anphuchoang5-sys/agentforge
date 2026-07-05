---
name: ship
description: 交付技能 — 把生成的代码打包成可下载的产出物，失败就明确报错，不冒充成功
level: L2
agents: [Pipeline]
---

# /ship 技能

> 注：这个技能不对应某个 LLM Agent，对应 `backend/pipeline/run.py` 里
> `_zip_output()` 这一段打包逻辑——记录的是这段代码本身应该遵守的规则，
> 不是给某个 Agent 看的 Prompt。

## 激活时机
Validator 判定通过（或达到最大重试轮数）之后，流程收尾，打包交付物。

## 执行规则
1. **打包前确认产出物非空**：`backend_code`/`frontend_code` 都为空时拒绝打包，
   不生成"格式合法但内容为空"的空 zip 冒充交付物
2. **交付物路径可预测**：zip 文件名和输出目录同名（`{app_output_dir}.zip`），
   不额外加时间戳/随机后缀，调用方能直接推算出交付物路径
3. **打包内容对应完整目录**：把 `app_output_dir` 下所有生成的文件打包，不只挑
   部分文件
4. **失败路径要显式报错**：打包失败（目录不存在、权限问题）必须抛出明确异常，
   不能静默返回一个假的成功交付物

## 质量检查点
- [ ] zip 包含 db.py/app.py/test_app.py（对应哪些专家实际执行过）
- [ ] 打包前检查过 output_dir 确实存在且非空
- [ ] 返回的 deliverable 路径真实存在，不是拼出来但没写文件的假路径
