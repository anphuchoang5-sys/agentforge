"""
commander — 同学A：需求理解与拆解模块

对外接口（供B调用）:
    decompose(user_input: str) -> TaskDecomposition
        → .api_spec.functions  (接口规范)
        → .tasks               (任务清单)
        → .estimated_iterations (预估轮数)

    decompose_with_metrics(user_input: str) -> dict
        → {"result": {...}, "metrics": {...}}

    health_check() -> bool

使用方式:
    from backend.agents.commander import decompose
    result = decompose("做一个待办事项应用")
"""

from .decompose import decompose, decompose_with_metrics
from .ollama_client import health_check

__all__ = ["decompose", "decompose_with_metrics", "health_check"]
