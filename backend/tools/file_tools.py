"""
file_tools.py — 文件读写工具
B 核心产出物

Agent 生成的代码通过这里落盘，Validator 通过这里读取代码审查。
"""

import os
from pathlib import Path


_WORKSPACE_ROOT = Path(
    os.getenv("AGENTFORGE_WORKSPACE_ROOT", Path(__file__).parents[2])
).resolve()


def _resolve_workspace_path(path: str) -> Path:
    """Resolve a tool path and require it to stay inside the workspace."""
    if not path or not path.strip():
        raise ValueError("文件路径不能为空")

    resolved = Path(path).expanduser().resolve()
    if not resolved.is_relative_to(_WORKSPACE_ROOT):
        raise PermissionError(
            f"拒绝访问工作区外路径: {resolved}；允许根目录: {_WORKSPACE_ROOT}"
        )
    return resolved


def write_file(path: str, content: str) -> str:
    """把代码内容写入磁盘，自动创建父目录。

    Args:
        path: 目标路径，如 ./output/generated_app/db.py
        content: 文件内容（代码字符串）

    Returns:
        写入的绝对路径
    """
    if content is None or not content.strip():
        raise ValueError(f"拒绝写入空内容文件: {path}")

    abs_path = _resolve_workspace_path(path)
    os.makedirs(abs_path.parent, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[write_file] {abs_path} ({len(content)} chars)")
    return str(abs_path)


def read_file(path: str) -> str:
    """从磁盘读取文件内容。

    Args:
        path: 文件路径

    Returns:
        文件内容字符串

    Raises:
        FileNotFoundError: 文件不存在时明确报错
    """
    abs_path = _resolve_workspace_path(path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"文件不存在: {abs_path}")
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"[read_file] {abs_path} ({len(content)} chars)")
    return content
