"""
decompose.py — 指挥官Agent核心拆解逻辑
同学A 核心产出物

把用户需求 → 接口规范 + 任务清单（Pydantic 结构化输出）
对齐 CLAUDE.md: 优先尝试 langchain 的 .with_structured_output()

B调用方式:
    from backend.agents.commander import decompose
    result = decompose("做一个待办事项应用")
    # → TaskDecomposition(api_spec=..., tasks=..., estimated_iterations=...)
"""

import json
import os
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 同时支持两种导入方式：
#   - 作为模块被 B 导入: from backend.agents.commander.decompose import decompose
#   - 直接运行: python decompose.py
try:
    from .commander_prompt import COMMANDER_SYSTEM_PROMPT
    from .schemas import TaskDecomposition
    from .ollama_client import generate, generate_with_metrics as _gem, health_check
except ImportError:
    from commander_prompt import COMMANDER_SYSTEM_PROMPT
    from schemas import TaskDecomposition
    from ollama_client import generate, generate_with_metrics as _gem, health_check


def _parse_json_fallback(raw: str) -> Optional[dict]:
    """从模型回复中提取JSON（兼容```json代码块等格式）"""
    text = raw.strip()

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()

    if "{" in text and "}" in text:
        start = text.index("{")
        end = text.rindex("}") + 1
        text = text[start:end]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _try_structured_output(user_input: str, model: str) -> Optional[TaskDecomposition]:
    """方式一：用 langchain 的 .with_structured_output()（CLAUDE.md 推荐方式）"""
    try:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        deepseek_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        if deepseek_key and "deepseek" in model.lower():
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=model,
                api_key=deepseek_key,
                base_url=deepseek_url,
                temperature=0.3,
                max_tokens=4096,
            )
        else:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(
                model=model,
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                temperature=0.3,
                num_predict=2048,
            )

        structured_llm = llm.with_structured_output(TaskDecomposition)
        result: TaskDecomposition = structured_llm.invoke(
            f"{COMMANDER_SYSTEM_PROMPT}\n\n用户需求：{user_input}"
        )
        if result.tasks:
            return result
    except Exception as e:
        print(f"[INFO] 结构化输出不可用，降级到JSON解析模式: {e}")
    return None


def _get_models_to_try(model: str) -> list[str]:
    """DeepSeek 单一模型；Ollama 自动降级 7B→1.5B"""
    if "deepseek" in model.lower():
        return [model]
    return [model, "Qwen2.5-Coder:1.5B"] if ("7b" in model.lower() or "7B" in model) else [model]


def decompose(user_input: str, model: str = None) -> TaskDecomposition:
    """把用户需求 → 接口规范 + 任务清单（Pydantic 结构化输出）

    B调用这个函数:
        from backend.agents.commander import decompose
        result = decompose("做一个待办事项应用")

        result.api_spec.functions     # 接口规范
        result.tasks                  # 任务列表
        result.estimated_iterations   # 预估轮数
        result.model_dump()           # 转 JSON
    """
    if model is None:
        model = os.getenv("COMMANDER_MODEL", "deepseek-chat" if os.getenv("DEEPSEEK_API_KEY") else "Qwen2.5-Coder:7B")

    for current_model in _get_models_to_try(model):
        print(f"[INFO] 尝试使用模型: {current_model}")

        structured = _try_structured_output(user_input, current_model)
        if structured is not None:
            return structured

        full_prompt = f"{COMMANDER_SYSTEM_PROMPT}\n\n用户需求：{user_input}"

        for attempt in range(3):
            try:
                raw = generate(full_prompt, current_model)
                parsed = _parse_json_fallback(raw)

                if parsed is None:
                    print(f"[WARN] 第{attempt+1}次: JSON解析失败")
                    continue

                result = TaskDecomposition.model_validate(parsed)
                print(f"[INFO] 需求拆解成功（模型={current_model}, 第{attempt+1}次尝试）")
                return result

            except Exception as e:
                print(f"[WARN] {current_model} 第{attempt+1}次: {e}")

        print(f"[WARN] {current_model} 3次均失败，尝试下一个模型")

    raise RuntimeError(
        "需求拆解失败：所有模型均无响应。\n"
        "请确认 DEEPSEEK_API_KEY 已配置，或启动 ollama serve。"
    )


def decompose_with_metrics(user_input: str, model: str = None) -> dict:
    """带耗时和Token统计的版本（供D展示）"""
    if model is None:
        model = os.getenv("COMMANDER_MODEL", "deepseek-chat" if os.getenv("DEEPSEEK_API_KEY") else "Qwen2.5-Coder:7B")

    full_prompt = f"{COMMANDER_SYSTEM_PROMPT}\n\n用户需求：{user_input}"

    for current_model in _get_models_to_try(model):
        try:
            metrics = _gem(full_prompt, current_model)
            raw = metrics["response"]

            parsed = _parse_json_fallback(raw)
            if not parsed:
                raise RuntimeError(f"模型返回内容无法解析为 JSON，模型={current_model}")

            result = TaskDecomposition.model_validate(parsed)
            return {
                "result": result.model_dump(),
                "metrics": {
                    "duration_ms": metrics["duration_ms"],
                    "tokens": metrics["tokens"],
                    "model": metrics["model"],
                },
            }
        except Exception as e:
            print(f"[WARN] {current_model} 调用失败: {e}")
            continue

    raise RuntimeError(
        "需求拆解失败：所有模型均无响应。\n"
        "请确认 DEEPSEEK_API_KEY 已配置，或启动 ollama serve。"
    )


# ===== 自测 =====
if __name__ == "__main__":
    alive = health_check()
    source = "DeepSeek API" if os.getenv("DEEPSEEK_API_KEY") else "Ollama"
    print(f"LLM 状态: {'online' if alive else 'offline'} ({source})")

    if alive:
        result = decompose("帮我做一个待办事项桌面应用，支持添加、完成、删除任务")
        print("\n" + "=" * 50)
        print("拆解结果:")
        print("=" * 50)
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print("LLM 不可用，请检查 DEEPSEEK_API_KEY 或启动 ollama serve。")
