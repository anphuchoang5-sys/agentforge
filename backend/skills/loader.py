"""
loader.py — Skill 加载器
B 核心产出物

在运行时读取 backend/skills/{name}/SKILL.md 的正文部分，追加进对应 Agent 的
System Prompt，让 SKILL.md 从"写了没人读"的静态文档变成真正生效的运行时内容
（problem.md 第6条）。
"""

import os

_SKILLS_DIR = os.path.dirname(__file__)


def load_skill_prompt(skill_name: str) -> str:
    """读取指定 Skill 的 SKILL.md，返回去掉 YAML frontmatter 之后的正文

    Args:
        skill_name: Skill 目录名，如 "build"/"spec"/"test"

    Returns:
        正文 Markdown 文本。文件不存在时让 FileNotFoundError 原样抛出，不静默
        兜底成空字符串——否则调用方会以为 Skill 生效了，实际上什么都没加载到
    """
    path = os.path.join(_SKILLS_DIR, skill_name, "SKILL.md")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return _strip_frontmatter(text).strip()


def _strip_frontmatter(text: str) -> str:
    """去掉 SKILL.md 开头的 --- ... --- YAML frontmatter，只留正文 Markdown"""
    if not text.startswith("---"):
        return text
    end = text.index("\n---", 3)
    return text[end + 4:]
