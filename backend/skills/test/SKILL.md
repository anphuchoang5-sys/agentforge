---
name: test
description: 测试生成技能 — 测试是功能可用的证明，不是摆设
level: L2
agents: [TestExpert, UIValidator]
---

# /test 技能

## 激活时机
当 Agent 收到「为某代码写测试」或「验证界面」类任务时激活。

## 执行规则
1. **读现有代码再写测试**：从 ProjectState 读 backend_code，不凭空猜测接口
2. **测试必须真实运行**：用 run_command 跑 pytest，把结果写进 test_results
3. **覆盖核心路径**：增删改查各至少一个测试用例
4. **测试隔离**：每个测试用独立的临时数据库，不污染彼此

## 输出格式
```python
# 文件名：test_app.py
import pytest
from db import create_todo, get_all_todos

@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yield

def test_create_todo():
    ...
```

## 质量检查点
- [ ] 所有测试函数以 test_ 开头
- [ ] 有 fixture 做初始化和清理
- [ ] pytest 运行结果写入 ProjectState["test_results"]
