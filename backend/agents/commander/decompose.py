"""
decompose.py — 指挥官Agent核心拆解逻辑
同学A 核心产出物

把用户需求 → 接口规范 + 任务清单（Pydantic 结构化输出）
直接调用 DeepSeek 要求纯 JSON 回复再手动解析——不走 langchain 的
.with_structured_output()，DeepSeek 官方不支持它要求的 response_format
（详见 decompose() 内的实现说明）

B调用方式:
    from backend.agents.commander import decompose
    result = decompose("做一个待办事项应用")
    # → TaskDecomposition(api_spec=..., tasks=..., estimated_iterations=...)
"""

import json
import os
import time
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError as exc:
    raise RuntimeError(
        "缺少 python-dotenv 依赖，无法加载运行环境；请先执行 pip install -r requirements.txt"
    ) from exc

load_dotenv()

try:
    # 独立运行（python decompose.py，项目根不在 sys.path 上）时这个绝对
    # 导入会失败，直接跳过——本文件目前没有 emoji 打印，跳过不影响功能，
    # 只是为将来万一加了 emoji 打印预先接好口子（problem.md 第31条）。
    from backend.tools.console_encoding import ensure_utf8_console
    ensure_utf8_console()
except ImportError:
    pass

try:
    # 同样只在独立运行、项目根不在 sys.path 上时才会走 except 分支——
    # 正常通过 workflow.py 调用时 backend 包必然可导入，_SPEC_SKILL 就是
    # spec/SKILL.md 的正文，不会退化成空字符串
    from backend.skills.loader import load_skill_prompt
except ImportError as exc:
    raise RuntimeError("无法导入 Skill loader，拒绝在 spec Skill 缺失时继续运行") from exc

_SPEC_SKILL = load_skill_prompt("spec")

# 同时支持两种导入方式：
#   - 作为模块被 B 导入: from backend.agents.commander.decompose import decompose
#   - 直接运行: python decompose.py
try:
    from .commander_prompt import COMMANDER_SYSTEM_PROMPT
    from .schemas import TaskDecomposition
    from .llm_client import generate_with_metrics as _gem, health_check
    from .call_log import log_call
except ImportError as exc:
    if "attempted relative import" not in str(exc):
        raise
    from commander_prompt import COMMANDER_SYSTEM_PROMPT
    from schemas import TaskDecomposition
    from llm_client import generate_with_metrics as _gem, health_check
    from call_log import log_call


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


def decompose(user_input: str, model: str = None) -> TaskDecomposition:
    """把用户需求 → 接口规范 + 任务清单（Pydantic 结构化输出）

    B调用这个函数:
        from backend.agents.commander import decompose
        result = decompose("做一个待办事项应用")

        result.api_spec.functions     # 接口规范
        result.tasks                  # 任务列表
        result.estimated_iterations   # 预估轮数
        result.model_dump()           # 转 JSON

    实现说明——为什么没有"先试 langchain .with_structured_output()，失败再退化"：
    这里原本确实有过这么一层，但 DeepSeek 官方 API 文档明确写着 response_format
    只支持 text/json_object 两种，不支持 OpenAI 新式的 json_schema 结构化输出——
    对 DeepSeek 调用 .with_structured_output() 必然会得到
    `400 This response_format type is unavailable now`，不是"偶尔失败"，是
    100% 必然失败。真实测过：那一层名义上是"优先尝试"，实际上从来没有成功过一次，
    每次都是靠下面这条"直接问 JSON、自己解析"的路径救回来的——它不是备用方案，
    是唯一真正跑得通的路径。既然如此就不再假装还有一次"优先尝试"，省掉一次
    注定失败、纯粹浪费 Token 和时间的 API 调用，直接用这条路径。
    """
    if model is None:
        model = os.getenv("COMMANDER_MODEL", "deepseek-v4-pro" if os.getenv("DEEPSEEK_API_KEY") else "Qwen2.5-Coder:7B")

    full_prompt = f"{COMMANDER_SYSTEM_PROMPT}\n\n{_SPEC_SKILL}\n\n用户需求：{user_input}"
    last_error: Optional[Exception] = None

    for attempt in range(3):
        start = time.time()
        try:
            # 用 generate_with_metrics 而不是裸 generate：同一个 API 调用，
            # 多返回 duration_ms/tokens，才记得进账（见 problem.md 第12条）
            metrics = _gem(full_prompt, model)
            raw = metrics["response"]
            parsed = _parse_json_fallback(raw)

            log_call(
                caller="commander",
                model=metrics["model"],
                prompt=user_input[:100],
                duration_ms=metrics["duration_ms"],
                tokens=metrics["tokens"],
                success=parsed is not None,
            )

            if parsed is None:
                last_error = ValueError(f"第{attempt + 1}次尝试：模型返回内容无法解析为 JSON")
                print(f"[WARN] {model} 第{attempt + 1}次: JSON解析失败")
                continue

            result = TaskDecomposition.model_validate(parsed)
            print(f"[INFO] 需求拆解成功（模型={model}, 第{attempt + 1}次尝试）")
            return result

        except Exception as e:
            last_error = e
            print(f"[WARN] {model} 第{attempt + 1}次: {e}")
            log_call(
                caller="commander",
                model=model,
                prompt=user_input[:100],
                duration_ms=round((time.time() - start) * 1000),
                tokens=0,
                success=False,
                error_msg=str(e)[:200],
            )

    raise RuntimeError(
        f"需求拆解失败：{model} 连续 3 次未能生成有效结果，最后一次错误：{last_error}\n"
        "请确认 DEEPSEEK_API_KEY 已配置。"
    ) from last_error


# ===== 自测 =====
if __name__ == "__main__":
    alive = health_check()
    print(f"LLM 状态: {'online' if alive else 'offline'} (DeepSeek API)")

    if alive:
        result = decompose("帮我做一个待办事项桌面应用，支持添加、完成、删除任务")
        print("\n" + "=" * 50)
        print("拆解结果:")
        print("=" * 50)
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
    else:
        print("LLM 不可用，请检查 DEEPSEEK_API_KEY 是否已配置。")
