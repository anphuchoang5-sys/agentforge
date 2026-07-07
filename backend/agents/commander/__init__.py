"""
commander — 同学A：需求理解与拆解模块

对外接口（供B调用）:
    decompose(user_input: str) -> TaskDecomposition
        → .api_spec.functions  (接口规范)
        → .tasks               (任务清单)
        → .estimated_iterations (预估轮数)

    health_check() -> bool

使用方式:
    from backend.agents.commander import decompose
    result = decompose("做一个待办事项应用")
"""

from .decompose import decompose
from .llm_client import health_check

__all__ = ["decompose", "health_check"]
