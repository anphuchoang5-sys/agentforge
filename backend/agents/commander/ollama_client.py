"""
ollama_client.py — 统一的模型调用接口
同学A 核心产出物 · 全组依赖

直接用 requests 调 Ollama API（比 langchain-ollama 更稳定）
"""

import time
import requests
from typing import Optional

OLLAMA_BASE = "http://localhost:11434"
OLLAMA_GENERATE = f"{OLLAMA_BASE}/api/generate"


def generate(prompt: str, model: str = "Qwen2.5-Coder:7B") -> str:
    """调用本地模型，返回生成的文本"""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3,
    }
    resp = requests.post(OLLAMA_GENERATE, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["response"]


def generate_with_metrics(prompt: str, model: str = "Qwen2.5-Coder:7B") -> dict:
    """带耗时和Token统计的调用（供D展示用）

    返回:
        {
            "response": "模型生成的文本",
            "duration_ms": 1234,
            "tokens": 256,
            "model": "Qwen2.5-Coder:7B"
        }
    """
    start = time.time()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3,
    }
    resp = requests.post(OLLAMA_GENERATE, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    elapsed = time.time() - start

    return {
        "response": data["response"],
        "duration_ms": round(elapsed * 1000),
        "tokens": data.get("eval_count", 0),
        "model": model,
    }


def health_check() -> bool:
    """检查 Ollama 服务是否在线"""
    try:
        r = requests.get(OLLAMA_BASE, timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False
