# 两个需要一起改接口的问题

> 都是今天接上真实验收标准核对之后跑出来的，确认是真实存在的问题，


---

## 问题1：`read_app_code()` 的 8000 字符截断，长文件会被切掉

**现状**：`checkers.py::read_app_code(app_path, max_chars=8000)`，如果 `app_path` 是目录，
会把 `db.py`/`app.py`/`test_app.py` 全部拼一起再截断。实测生成的应用三个文件加起来经常
超过 8000 字符，`test_app.py` 因为排序在最后，经常被整个切掉，导致 LLM 核对"测试是否正确"
这类验收标准时只能回答"文件被截断，无法确认"。

**建议方案**（两个都行，你定）：
- **省事版**：把 `max_chars` 调大（比如 5万），能覆盖大部分场景，但本质没根治，文件更大还会超
- **根治版**：`validate()` 加一个可选参数（比如 `code_content: Optional[str] = None`），
  有传就直接用，不用再读硬盘/截断。B 这边 `backend_code`/`frontend_code`/`test_code`
  三份代码在生成完的一瞬间就已经在内存里了（`ProjectState` 白板上现成的），可以直接拼好传给你，
  不用你这边重新读文件

---

## 问题2：TestExpert 真实跑的 pytest 结果，没有任何通路能传到你的 `pytest_check()`

**现状**：`pytest_check(app_path, pytest_result_path=None)` 目前是桩函数，注释写的是
"MVP阶段：B还没产出"——但 TestExpert 其实一直都在真实跑 pytest（`run_command("python -m pytest ...")`），
只是：
1. TestExpert 只存了 stdout/stderr 纯文本，从没生成过 `pytest --json-report` 要求的 JSON 文件
2. B 这边 `validator_stub.py` 就算拿到 `test_results` 文本也没转发给你（现在走的是直接 Python
   调用你的 `c_validate(app_path, criteria)`，没有传测试结果这个入参）
3. 你的公开接口 `validate(app_path, criteria, iteration)` 本身也没留给外部传测试结果的口子

结果就是不管 TestExpert 测试实际过没过，`pytest_check` 永远显示"跳过，视为通过"。

**建议方案**：
- B 这边把 `TestExpert` 的 pytest 调用加上 `--json-report --json-report-file=xxx.json`，
  跑完把这个 json 路径存进 `ProjectState`
- 你这边 `validate()` 加一个可选参数（比如 `pytest_result_path: Optional[str] = None`），
  透传给 `pytest_check()`，有就读 json 解析真实结果，没有就还是跳过（保持向后兼容，
  不影响你现在自测/独立开发时的用法）

---

都是加**可选参数**，不改变现有调用方式，不会破坏你已经写好的东西，随时可以接。
