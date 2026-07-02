"""
file_tools.py — 文件读写工具
B 核心产出物

Agent 生成的代码通过这里落盘，Validator 通过这里读取代码审查。
"""

import os


def write_file(path: str, content: str) -> str:
    """把代码内容写入磁盘，自动创建父目录。

    Args:
        path: 目标路径，如 ./output/generated_app/db.py
        content: 文件内容（代码字符串）

    Returns:
        写入的绝对路径
    """
    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[write_file] {abs_path} ({len(content)} chars)")
    return abs_path


def read_file(path: str) -> str:
    """从磁盘读取文件内容。

    Args:
        path: 文件路径

    Returns:
        文件内容字符串

    Raises:
        FileNotFoundError: 文件不存在时明确报错
    """
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"文件不存在: {abs_path}")
    with open(abs_path, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"[read_file] {abs_path} ({len(content)} chars)")
    return content
