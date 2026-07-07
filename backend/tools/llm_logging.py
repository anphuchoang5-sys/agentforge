"""
llm_logging.py — 给 LLM 调用包一层耗时 + Token 统计
B 核心产出物 · 落盘复用 A 的 backend/agents/commander/call_log.py

各专家 Agent 直接用 langchain_openai.ChatOpenAI，没走 A 的 llm_client.py，
所以调用记录不会自动落进 call_log 的 SQLite 表——用这个包一层就行，
调用方用法跟直接 llm.invoke(messages) 完全一样，只是多记一笔。
"""

import time
from typing import Any

from backend.agents.commander.call_log import log_call


def timed_invoke(llm: Any, messages: list, caller: str) -> Any:
    """等价于 llm.invoke(messages)，额外把耗时和 Token 记进 call_log"""
    start = time.time()
    model_name = getattr(llm, "model_name", None) or getattr(llm, "model", "unknown")

    try:
        response = llm.invoke(messages)
    except Exception as e:
        log_call(
            caller=caller,
            model=model_name,
            prompt=str(messages)[:100],
            duration_ms=round((time.time() - start) * 1000),
            tokens=0,
            success=False,
            error_msg=str(e)[:200],
        )
        raise

    usage = getattr(response, "usage_metadata", None) or {}
    tokens = usage.get("total_tokens", 0)

    log_call(
        caller=caller,
        model=model_name,
        prompt=str(messages)[:100],
        duration_ms=round((time.time() - start) * 1000),
        tokens=tokens,
        success=True,
    )
    return response
