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
    app_name: Optional[str] = Field(
        default=None,
        description="应用名/输出目录名，英文 snake_case 短词，体现核心业务实体，如 todo、account_book；"
        "识别不出时留空，由 B 从 api_spec.functions 派生兜底",
    )
    api_spec: ApiSpec = Field(
        description="接口规范（接口优先设计：先定义api_spec再分配任务）"
    )
    tasks: List[SubTask] = Field(description="子任务列表")
    estimated_iterations: int = Field(
        default=1,
        description="预估修复轮数",
    )


