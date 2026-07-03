"""
routes/metrics.py — Token 消耗统计接口
B 核心产出物 · 给 D 的 Token 消耗图表用

复用 A 的 backend/agents/commander/call_log.py（不改她的文件），
按 caller 聚合 tokens，聚合逻辑放在这里，不掺进 A 的模块。
"""

from fastapi import APIRouter

from backend.agents.commander.call_log import get_recent_logs

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics/tokens")
async def token_metrics() -> dict:
    """按调用方（Commander/BackendExpert/FrontendExpert/TestExpert）汇总 Token 消耗

    数据来自真实调用记录（backend/tools/llm_logging.py 里每次 LLM 调用都会记一笔），
    还没跑过流程时是空列表，不用假数据垫底。
    """
    logs = get_recent_logs(limit=1000)
    by_caller: dict[str, int] = {}
    for row in logs:
        if not row.get("success"):
            continue
        caller = row["caller"]
        by_caller[caller] = by_caller.get(caller, 0) + (row.get("tokens") or 0)

    return {"data": [{"name": caller, "tokens": tokens} for caller, tokens in by_caller.items()]}
