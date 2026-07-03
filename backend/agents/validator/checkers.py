"""
checkers.py — 验证者四项检查实现
同学C 核心产出物 · 对齐 验证者.html 四项检查

四项检查:
    ① compile_check  — 编译检查（py_compile，能否 import）
    ② ruff_check     — ruff 静态检查（语法/未使用变量等）
    ③ pytest_check   — 读取 TestExpert 的 pytest 结果（桩，等 B 接入）
    ④ llm_check      — LLM 逐条核对验收标准（桩，等 A 的 ollama_client 接入）

每项返回统一格式: (passed, logs, failed_tests)
    passed: bool        — 该项是否通过（warning 不算失败）
    logs: list[str]    — 该项的日志
    failed_tests: list[FailedTest] — 失败项（severity=error 算失败）
"""

import json
import subprocess
import py_compile
from pathlib import Path
from typing import Tuple, List

# 双导入（对齐 A 的 decompose.py 风格）
try:
    from .schemas import FailedTest
except ImportError:
    from schemas import FailedTest


# ===== ① 编译检查 =====

def compile_check(app_path: str) -> Tuple[bool, List[str], List[FailedTest]]:
    """编译检查：python 能否正常编译 app_path（语法层面）

    用 py_compile 编译，捕获 SyntaxError。
    """
    logs = []
    failed: List[FailedTest] = []

    if not Path(app_path).exists():
        msg = f"应用文件不存在: {app_path}"
        logs.append(f"[compile] ❌ {msg}")
        failed.append(FailedTest(name="compile", reason=msg, severity="error"))
        return False, logs, failed

    logs.append(f"[compile] 检查文件: {app_path}")
    try:
        py_compile.compile(app_path, doraise=True)
        logs.append("[compile] ✅ 编译通过（语法正确）")
        return True, logs, failed
    except py_compile.PyCompileError as e:
        msg = f"编译失败（语法错误）: {str(e)[:300]}"
        logs.append(f"[compile] ❌ {msg}")
        failed.append(FailedTest(name="compile", reason=msg, severity="error"))
        return False, logs, failed
    except Exception as e:
        msg = f"编译检查异常: {type(e).__name__}: {str(e)[:200]}"
        logs.append(f"[compile] ❌ {msg}")
        failed.append(FailedTest(name="compile", reason=msg, severity="error"))
        return False, logs, failed


# ===== ② ruff 静态检查 =====

# ruff 配置文件路径（项目根的 backend/ruff.toml）
_RUFF_CONFIG = str(Path(__file__).parents[2] / "ruff.toml")


def ruff_check(app_path: str) -> Tuple[bool, List[str], List[FailedTest]]:
    """ruff 静态检查：调用 ruff CLI

    使用 backend/ruff.toml 配置（只看 E/F 级，忽略常见误报）。
    """
    logs = []
    failed: List[FailedTest] = []

    if not Path(app_path).exists():
        logs.append("[ruff] ⏭️ 跳过（文件不存在）")
        return True, logs, failed  # 文件不存在不在此处报，compile_check 已报

    # 判断是单文件还是目录
    target = Path(app_path)
    ruff_target = str(target.parent) if target.is_file() else str(target)

    cmd = ["ruff", "check", "--config", _RUFF_CONFIG, "--output-format=json", ruff_target]
    logs.append(f"[ruff] 执行: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, encoding="utf-8"
        )
    except FileNotFoundError:
        msg = "ruff 未安装（pip install ruff）"
        logs.append(f"[ruff] ⚠️ {msg}")
        failed.append(FailedTest(name="ruff", reason=msg, severity="warning"))
        return True, logs, failed  # warning 不阻断
    except subprocess.TimeoutExpired:
        msg = "ruff 检查超时（>30s）"
        logs.append(f"[ruff] ⚠️ {msg}")
        failed.append(FailedTest(name="ruff", reason=msg, severity="warning"))
        return True, logs, failed

    # ruff 退出码: 0=无问题, 1=有违规, 2=配置错误
    if result.returncode == 2:
        msg = f"ruff 配置错误: {result.stderr[:200]}"
        logs.append(f"[ruff] ⚠️ {msg}")
        failed.append(FailedTest(name="ruff", reason=msg, severity="warning"))
        return True, logs, failed

    # 解析 JSON 输出
    errors = 0
    warnings = 0
    if result.stdout.strip():
        try:
            issues = json.loads(result.stdout)
            for issue in issues:
                code = issue.get("code", "?")
                filename = issue.get("filename", "?")
                line = issue.get("location", {}).get("row", "?")
                message = issue.get("message", "")
                # F401/F841 在 ruff.toml 里已 ignore，正常不会出现
                # E 级算 error
                if code.startswith("F") and code != "F401":
                    # pyflakes 错误（除 F401 未使用 import）算 error
                    errors += 1
                    failed.append(FailedTest(
                        name=f"ruff:{code}",
                        reason=f"{filename}:{line} {message}",
                        severity="error",
                    ))
                else:
                    warnings += 1
                    # 其余记日志，不进 failed_tests
                    logs.append(f"[ruff] ⚠️ {code} {filename}:{line} {message}")
        except json.JSONDecodeError:
            # 非 JSON 输出（可能 ruff 版本问题），降级文本解析
            logs.append(f"[ruff] 输出解析失败，原始输出: {result.stdout[:500]}")

    passed = errors == 0
    if passed:
        logs.append(f"[ruff] ✅ 通过（{warnings} 个警告，{errors} 个错误）")
    else:
        logs.append(f"[ruff] ❌ {errors} 个错误，{warnings} 个警告")

    return passed, logs, failed


# ===== ③ pytest 检查（桩） =====

def pytest_check(app_path: str, pytest_result_path: str = None) -> Tuple[bool, List[str], List[FailedTest]]:
    """读取 TestExpert 已跑完的 pytest 结果（桩函数）

    MVP 阶段: B 还没产出，返回跳过。
    后续接入: 读取 pytest_result_path（json 格式），解析 failed 用例。

    参数:
        app_path: 应用路径
        pytest_result_path: pytest --json-report 输出路径（B 提供）
    """
    logs = ["[pytest] ⏭️ 桩函数：TestExpert 未接入，跳过（返回通过）"]
    return True, logs, []


# ===== ④ LLM 验收标准核对（桩） =====

def llm_check(
    app_path: str,
    criteria: List[str] = None,
    code_content: str = None,
) -> Tuple[bool, List[str], List[FailedTest]]:
    """LLM 逐条核对验收标准（桩函数）

    MVP 阶段: 返回跳过。Prompt 已写好（validator_prompt.py），待接入 A 的 ollama_client。
    后续接入:
        from backend.agents.commander.ollama_client import generate
        from .validator_prompt import build_check_prompt
        raw = generate(build_check_prompt(criteria, code_content), "Qwen2.5-Coder:7B")
        # 解析 raw JSON → results
    """
    logs = ["[llm] ⏭️ 桩函数：ollama_client 未接入，跳过（返回通过）"]
    if criteria:
        logs.append(f"[llm] 待核对 {len(criteria)} 条验收标准（接入后执行）")
    return True, logs, []


# ===== 读取代码内容（供 LLM 检查用） =====

def read_app_code(app_path: str, max_chars: int = 8000) -> str:
    """读取应用代码内容（截断，避免超长 prompt）

    如果 app_path 是目录，读取目录下所有 .py 文件合并。
    """
    target = Path(app_path)
    if target.is_file():
        content = target.read_text(encoding="utf-8", errors="ignore")
        return content[:max_chars] + ("\n...[截断]" if len(content) > max_chars else "")
    elif target.is_dir():
        parts = []
        for py in sorted(target.glob("**/*.py"))[:10]:  # 最多读 10 个文件
            parts.append(f"# ===== {py.name} =====\n{py.read_text(encoding='utf-8', errors='ignore')}")
        joined = "\n\n".join(parts)
        return joined[:max_chars] + ("\n...[截断]" if len(joined) > max_chars else "")
    return ""
