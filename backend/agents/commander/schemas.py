"""
schemas.py — Pydantic 数据模型（对齐 CLAUDE.md + 指挥官层.html）
同学A 定义 · 全组遵守 · 定死不改

融合两份文档：
- CLAUDE.md: TaskDecomposition + SubTask（含 acceptance_criteria）
- 指挥官层.html: api_spec（接口优先设计）
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal


# ===== 接口规范（指挥官层.html 接口优先设计） =====

class ParamDef(BaseModel):
    """函数参数定义"""
    name: str = Field(description="参数名，如 title")
    type: str = Field(description="参数类型，如 str, int, bool")


class FuncSpec(BaseModel):
    """单个函数接口规范"""
    params: List[ParamDef] = Field(description="参数列表")
    return_type: str = Field(description="返回值类型", alias="return")

    model_config = {"populate_by_name": True}


class ApiSpec(BaseModel):
    """接口规范集合 — key=函数名"""
    functions: dict[str, FuncSpec] = Field(
        default_factory=dict,
        description="函数名到接口定义的映射，如 create_todo → {params: [...], return: int}",
    )


# ===== 任务定义（CLAUDE.md TaskDecomposition） =====

class SubTask(BaseModel):
    """单个子任务（对齐 CLAUDE.md SubTask）"""
    id: str = Field(description="任务ID，如 task_1")
    type: Literal["frontend", "backend", "test", "ui_validate"] = Field(
        description="任务类型"
    )
    description: str = Field(description="自然语言描述")
    dependencies: List[str] = Field(
        default_factory=list,
        description="依赖的任务ID列表；空列表表示无依赖",
    )
    acceptance_criteria: List[str] = Field(
        default_factory=list,
        description="验收标准，供 Validator 逐条比对",
    )


class TaskDecomposition(BaseModel):
    """完整的任务拆解结果（对齐 CLAUDE.md TaskDecomposition）"""
    api_spec: ApiSpec = Field(
        description="接口规范（接口优先设计：先定义api_spec再分配任务）"
    )
    tasks: List[SubTask] = Field(description="子任务列表")
    estimated_iterations: int = Field(
        default=1,
        description="预估修复轮数",
    )


# ===== 兜底方案（模型抽风时用） =====

FALLBACK_DECOMPOSITION = TaskDecomposition(
    api_spec=ApiSpec(
        functions={
            "create_todo": FuncSpec(
                params=[ParamDef(name="title", type="str")],
                return_type="int",
            ),
            "get_all_todos": FuncSpec(
                params=[],
                return_type="List[dict]",
            ),
            "delete_todo": FuncSpec(
                params=[ParamDef(name="todo_id", type="int")],
                return_type="bool",
            ),
        }
    ),
    tasks=[
        SubTask(
            id="task_1",
            type="backend",
            description="实现SQLite数据库，支持create_todo/get_all_todos/delete_todo",
            dependencies=[],
            acceptance_criteria=["数据库文件创建成功", "增删改查函数可调用"],
        ),
        SubTask(
            id="task_2",
            type="frontend",
            description="用Tkinter创建待办事项界面，调用后端函数",
            dependencies=[],
            acceptance_criteria=["界面可显示任务列表", "添加/删除按钮可用"],
        ),
        SubTask(
            id="task_3",
            type="test",
            description="编写pytest测试覆盖所有数据库操作",
            dependencies=[],
            acceptance_criteria=["pytest测试全部通过"],
        ),
        SubTask(
            id="task_4",
            type="ui_validate",
            description="启动应用截图验证UI元素",
            dependencies=["task_2"],
            acceptance_criteria=["截图包含任务列表和按钮"],
        ),
    ],
    estimated_iterations=1,
)
