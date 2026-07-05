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
1. **读现有代码再写测试**：根据给出的 backend_code 编写测试，不凭空猜测接口
2. **写的代码必须经得起真实运行**：生成代码之后，外部流程会自动用 pytest 真实执行
   （不是你来跑），把结果记录下来——你要保证的是代码本身没有语法错误、没有 import
   不存在的模块，否则会在收集阶段就被判定生成失败
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
- [ ] 所有 import 的模块真实存在，不会导致 pytest 收集阶段失败
