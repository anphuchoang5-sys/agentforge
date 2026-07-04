"""
ollama_client.py — 统一 LLM 调用接口（DeepSeek 优先，Ollama 备用）
同学A 核心产出物 · 全组依赖

优先级：DEEPSEEK_API_KEY 存在 → DeepSeek API；否则 → 本地 Ollama
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

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_GENERATE = f"{OLLAMA_BASE}/api/generate"


def _is_deepseek(model: str) -> bool:
    return "deepseek" in model.lower()


def _default_model() -> str:
    return os.getenv("COMMANDER_MODEL", "deepseek-v4-pro" if DEEPSEEK_API_KEY else "Qwen2.5-Coder:7B")


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

    start = time.time()

    if DEEPSEEK_API_KEY and _is_deepseek(model):
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4096,
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

    # Ollama 路径
    resp = requests.post(
        OLLAMA_GENERATE,
        json={"model": model, "prompt": prompt, "stream": False, "temperature": 0.3},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "response": data["response"],
        "duration_ms": round((time.time() - start) * 1000),
        "tokens": data.get("eval_count", 0),
        "model": model,
    }


def health_check() -> bool:
    """DeepSeek key 存在即视为可用；否则检查 Ollama 是否在线。"""
    if DEEPSEEK_API_KEY:
        return True
    try:
        r = requests.get(OLLAMA_BASE, timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False
