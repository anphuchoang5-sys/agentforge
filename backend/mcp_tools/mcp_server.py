"""
mcp_server.py — MCP 工具服务
B 核心产出物

把 write_file / read_file / run_command 包装成 MCP 协议暴露出去。
其他 Agent（包括 C、D）可以通过 MCP 标准接口调用这些工具，
而不需要直接 import Python 函数——这是"USB 标准接口"的意义。

启动方式：
    python -m backend.mcp_tools.mcp_server

Agent 调用方式（langchain-mcp-adapters）：
    from mcp import ClientSession, StdioServerParameters
    from langchain_mcp_adapters.tools import load_mcp_tools
    ...
"""

from mcp.server.fastmcp import FastMCP
from backend.tools.file_tools import write_file, read_file
from backend.tools.command_tools import run_command as _run_command
from backend.tools.console_encoding import ensure_utf8_console

ensure_utf8_console()

mcp = FastMCP("agentforge-tools")


@mcp.tool()
def tool_write_file(path: str, content: str) -> str:
    """把代码内容写入磁盘文件，自动创建父目录。

    Args:
        path: 目标路径，如 ./output/generated_app/db.py
        content: 文件内容（代码字符串）

    Returns:
        写入的绝对路径
    """
    return write_file(path, content)


@mcp.tool()
def tool_read_file(path: str) -> str:
    """从磁盘读取文件内容。

    Args:
        path: 文件路径

    Returns:
        文件内容字符串
    """
    return read_file(path)


@mcp.tool()
def tool_run_command(cmd: str, cwd: str = ".", timeout: int = 60) -> dict:
    """在指定目录执行 shell 命令。

    Args:
        cmd: 命令字符串，如 "pytest test_app.py -v"
        cwd: 工作目录
        timeout: 超时秒数

    Returns:
        {"success": bool, "stdout": str, "stderr": str, "returncode": int}
    """
    return _run_command(cmd, cwd=cwd, timeout=timeout)


if __name__ == "__main__":
    print("[MCP Server] 启动 agentforge-tools...")
    mcp.run()
