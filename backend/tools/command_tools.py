"""
command_tools.py — 命令执行工具
B 核心产出物

让 Agent 能真实运行代码（pip install、python main.py、pytest 等）。
subprocess 隔离执行，捕获 stdout + stderr，设置超时防挂死。
"""

import subprocess
import sys


def run_command(cmd: str, cwd: str = ".", timeout: int = 60) -> dict:
    """在指定目录执行 shell 命令，返回结构化结果。

    Args:
        cmd: 要执行的命令，如 "python db.py" 或 "pytest test_app.py -v"
        cwd: 工作目录（命令在哪个文件夹里跑）
        timeout: 超时秒数，防止 Agent 生成的死循环代码把进程挂死

    Returns:
        {
            "success": True/False,
            "stdout": "...",
            "stderr": "...",
            "returncode": 0,
            "cmd": "pytest ...",
        }
    """
    print(f"[run_command] {cmd}  (cwd={cwd})")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        success = result.returncode == 0
        if success:
            print(f"[run_command] OK  stdout={result.stdout[:200]!r}")
        else:
            print(f"[run_command] FAIL  stderr={result.stderr[:200]!r}")
        return {
            "success": success,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "cmd": cmd,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"命令超时（>{timeout}s）: {cmd}",
            "returncode": -1,
            "cmd": cmd,
        }
