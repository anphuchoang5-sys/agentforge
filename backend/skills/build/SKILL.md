---
name: build
description: 代码构建技能 — 一次实现一个功能切片，生成可运行的 Python 代码
level: L2
agents: [BackendExpert, FrontendExpert]
---

# /build 技能

## 激活时机
当 Agent 收到「实现某功能」类任务时自动激活。

## 执行规则
1. **先读接口规范**：从 ProjectState 读取 api_spec，不自己发明函数名
2. **一次只写一个文件**：backend → db.py，frontend → app.py
3. **代码必须可直接运行**：不留 TODO，不引入未在 requirements.txt 里的依赖
4. **用 ```python ``` 包裹输出**：方便解析器提取代码

## 输出格式
```python
# 文件名：db.py
import sqlite3

def create_todo(title: str) -> int:
    ...
```

## 质量检查点
- [ ] 函数名与接口规范完全一致
- [ ] 有错误处理（至少捕获数据库异常）
- [ ] 代码能通过 `ruff check` 静态检查
