"""
llm_client.py — 统一 LLM 调用接口（仅 DeepSeek 云端 API）
同学A 核心产出物 · 全组依赖

violent 分支策略：只用云端 DeepSeek API，不使用本地模型（Ollama）。
model 不是 DeepSeek 系列或 DEEPSEEK_API_KEY 缺失时，明确 raise，不做任何
静默降级/兜底（原文件名 ollama_client.py 曾经真的有 Ollama 分支，problem.md
第14条记录过这个文件名/内容跟实际策略不一致的问题，这次改名 + 删掉 Ollama
分支一起解决）。
"""

import os
import time
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")


def _is_deepseek(model: str) -> bool:
    return "deepseek" in model.lower()


def _default_model() -> str:
    return os.getenv("COMMANDER_MODEL", "deepseek-v4-pro")


def generate_with_metrics(prompt: str, model: str = None) -> dict:
    """带耗时和 Token 统计的调用（供 D 展示用）

    返回:
        {
            "response": "模型生成的文本",
            "duration_ms": 1234,
            "tokens": 256,
            "model": "deepseek-v4-pro"
        }
    """
    if model is None:
        model = _default_model()

    if not _is_deepseek(model):
        raise RuntimeError(
            f"violent 分支只支持 DeepSeek 系列模型，不支持本地模型: {model!r}"
        )
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY，无法调用 DeepSeek API")

    start = time.time()
    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/chat/completions",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4096,
            # DeepSeek 官方只支持 response_format: json_object（不支持
            # OpenAI 新式的 json_schema/结构化输出，那种模式会直接 400
            # "This response_format type is unavailable now"）。调用方
            # prompt 里已经明确要求"只输出 JSON"，满足 DeepSeek 要求
            # prompt 里必须出现"json"字样的前提，加这个参数能让返回的
            # JSON 格式更稳，减少 _parse_json_fallback() 解析失败重试的次数
            "response_format": {"type": "json_object"},
        },
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    return {
        "response": data["choices"][0]["message"]["content"],
        "duration_ms": round((time.time() - start) * 1000),
        "tokens": usage.get("total_tokens", 0),
        "model": model,
    }


def health_check() -> bool:
    """检查当前显式模型配置是否可用（只认 DeepSeek，不做本地模型兜底）。"""
    model = _default_model()
    if not _is_deepseek(model):
        return False
    return bool(DEEPSEEK_API_KEY)
