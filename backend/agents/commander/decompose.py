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
from typing import Optional

# 同时支持两种导入方式：
#   - 作为模块被 B 导入: from backend.agents.commander.decompose import decompose
#   - 直接运行: python decompose.py
try:
    # 方式一：相对导入（作为包的一部分被导入时用）
    from .commander_prompt import COMMANDER_SYSTEM_PROMPT
    from .schemas import TaskDecomposition, FALLBACK_DECOMPOSITION
    from .ollama_client import generate, generate_with_metrics as _gem, health_check
except ImportError:
    # 方式二：绝对导入（直接运行时用）
    from commander_prompt import COMMANDER_SYSTEM_PROMPT
    from schemas import TaskDecomposition, FALLBACK_DECOMPOSITION
    from ollama_client import generate, generate_with_metrics as _gem, health_check


def _parse_json_fallback(raw: str) -> Optional[dict]:
    """从模型回复中提取JSON（兼容```json代码块等格式）"""
    text = raw.strip()

    # 尝试找 ```json ... ``` 包裹的内容
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start) if "```" in text[start:] else len(text)
        text = text[start:end].strip()

    # 尝试找 { ... }
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
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=model,
            base_url="http://localhost:11434",
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


def decompose(user_input: str, model: str = "Qwen2.5-Coder:7B") -> TaskDecomposition:
    """把用户需求 → 接口规范 + 任务清单（Pydantic 结构化输出）

    自动降级：7B 失败后自动尝试 1.5B，再失败走兜底。

    B调用这个函数:
        from backend.agents.commander import decompose
        result = decompose("做一个待办事项应用")

        # 读取结果
        result.api_spec.functions     # 接口规范
        result.tasks                  # 任务列表
        result.estimated_iterations   # 预估轮数

        # 转 JSON
        result.model_dump()
    """
    # 模型降级列表：7B 失败 → 1.5B → 兜底
    models_to_try = [model, "Qwen2.5-Coder:1.5B"] if "7b" in model.lower() or "7B" in model else [model]

    for current_model in models_to_try:
        print(f"[INFO] 尝试使用模型: {current_model}")

        # 方式一：用 langchain 结构化输出
        structured = _try_structured_output(user_input, current_model)
        if structured is not None:
            return structured

        # 方式二：JSON 解析模式
        full_prompt = f"{COMMANDER_SYSTEM_PROMPT}\n\n用户需求：{user_input}"

        for attempt in range(3):
            try:
                raw = generate(full_prompt, current_model)
                parsed = _parse_json_fallback(raw)

                if parsed is None:
                    print(f"[WARN] 第{attempt+1}次: JSON解析失败")
                    continue

                # 转成 Pydantic 验证
                result = TaskDecomposition.model_validate(parsed)
                print(f"[INFO] 需求拆解成功（模型={current_model}, 第{attempt+1}次尝试）")
                return result

            except Exception as e:
                print(f"[WARN] {current_model} 第{attempt+1}次: {e}")

        print(f"[WARN] {current_model} 3次均失败，尝试下一个模型")

    # 全部失败 → 用兜底方案
    print("[WARN] 所有模型均失败，使用兜底方案")
    return FALLBACK_DECOMPOSITION


def decompose_with_metrics(
    user_input: str, model: str = "Qwen2.5-Coder:7B"
) -> dict:
    """带耗时和Token统计的版本（供D展示）"""
    models_to_try = [model, "Qwen2.5-Coder:1.5B"] if "7b" in model.lower() or "7B" in model else [model]
    full_prompt = f"{COMMANDER_SYSTEM_PROMPT}\n\n用户需求：{user_input}"

    for current_model in models_to_try:
        try:
            metrics = _gem(full_prompt, current_model)
            raw = metrics["response"]

            parsed = _parse_json_fallback(raw)
            if parsed:
                try:
                    result = TaskDecomposition.model_validate(parsed)
                except Exception:
                    result = FALLBACK_DECOMPOSITION
            else:
                result = FALLBACK_DECOMPOSITION

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

    # 全部失败，用兜底
    return {
        "result": FALLBACK_DECOMPOSITION.model_dump(),
        "metrics": {"duration_ms": 0, "tokens": 0, "model": model},
    }


# ===== 自测 =====
if __name__ == "__main__":
    alive = health_check()
    print(f"Ollama 状态: {'✅ 在线' if alive else '❌ 离线'}")

    if alive:
        result = decompose("帮我做一个待办事项桌面应用，支持添加、完成、删除任务")
        print("\n" + "=" * 50)
        print("拆解结果:")
        print("=" * 50)
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print("使用兜底方案:")
        print(
            json.dumps(
                FALLBACK_DECOMPOSITION.model_dump(), indent=2, ensure_ascii=False
            )
        )
