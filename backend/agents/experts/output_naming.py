"""
output_naming.py — 输出目录命名解析
B 核心产出物

专家池（BackendExpert/FrontendExpert/TestExpert）共用的输出目录解析逻辑。
放在专家池而不是 Commander 的 decompose_node 里：决定"代码写到哪个文件夹"
是执行层（怎么落盘）的关注点，不是需求拆解层（做什么）的关注点。

resolve_output_dir() 是纯函数，只依赖 base_dir + task_decomposition，
BackendExpert/FrontendExpert 各自独立调用也必然算出同一个目录，
不需要靠共享状态协调；跨重试轮次重复调用也是同一个结果，不会累加路径。
"""

import re
from collections import Counter

# 接口规范里的函数名都是 verb_noun 形式（spec/SKILL.md 定的命名规范），
# 去掉常见动词前缀剩下的名词就是业务领域词，可以直接当输出目录名。
# 这套逻辑只在 Commander 没给出 app_name 时（比如走 Ollama 兜底、JSON 解析
# 没覆盖到这个字段）当兜底，优先信号源是 decomp.app_name。
_CRUD_VERBS = {"create", "get", "update", "delete", "add", "remove", "list", "find", "fetch", "set", "all"}


def _derive_app_name(decomp) -> str:
    """从接口规范的函数名派生应用名，如 create_todo/get_all_todos/delete_todo → "todo\""""
    nouns = []
    for func_name in decomp.api_spec.functions:
        parts = [p for p in func_name.lower().split("_") if p and p not in _CRUD_VERBS]
        if not parts:
            continue
        noun = "_".join(parts)
        if noun.endswith("s") and len(noun) > 3:
            noun = noun[:-1]
        nouns.append(noun)
    return Counter(nouns).most_common(1)[0][0] if nouns else "generated_app"


def _sanitize_app_name(name: str) -> str:
    """把 LLM 给的 app_name 清理成安全的目录名片段（LLM 输出格式不保证严格遵守 snake_case）"""
    return re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")


def resolve_output_dir(base_dir: str, decomp) -> str:
    """算出这次任务实际要写入的目录：base_dir/应用名

    优先用 Commander 直接给出的 app_name，拿不到才退回 _derive_app_name 兜底。
    """
    app_name = _sanitize_app_name(decomp.app_name) if decomp.app_name else ""
    if not app_name:
        app_name = _derive_app_name(decomp)
    return f"{base_dir.rstrip('/')}/{app_name}"
