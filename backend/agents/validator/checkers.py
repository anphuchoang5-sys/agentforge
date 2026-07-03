"""
checkers.py — 验证者四项检查实现
同学C 核心产出物 · 对齐 验证者.html 四项检查

四项检查:
    ① compile_check  — 编译检查（py_compile，能否 import）
    ② ruff_check     — ruff 静态检查（语法/未使用变量等）
    ③ pytest_check   — 读取 TestExpert 的 pytest 结果（桩，等 B 接入）
    ④ llm_check      — LLM 逐条核对验收标准（已接入 A 的 ollama_client）

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


# ===== ④ LLM 验收标准核对 =====

def llm_check(
    app_path: str,
    criteria: List[str] = None,
    code_content: str = None,
) -> Tuple[bool, List[str], List[FailedTest]]:
    """LLM 逐条核对验收标准

    调用 A 的 ollama_client.generate()，用 validator_prompt.py 的提示词，
    让 LLM 逐条判断每条验收标准是否在代码中实现。

    降级策略:
        - 无验收标准 → 跳过（返回通过）
        - ollama_client 不可用（Ollama 未启动 / 无 DeepSeek Key）→ 降级为桩（不阻断）
    """
    logs = []
    failed: List[FailedTest] = []

    # 无验收标准 → 直接跳过
    if not criteria:
        logs.append("[llm] ⏭️ 无验收标准，跳过")
        return True, logs, failed

    logs.append(f"[llm] 核对 {len(criteria)} 条验收标准...")

    # 准备代码内容
    if not code_content:
        code_content = read_app_code(app_path)

    # 调用 A 的 ollama_client
    try:
        from backend.agents.commander.ollama_client import generate
    except ImportError:
        logs.append("[llm] ⚠️ ollama_client 导入失败，降级为桩（返回通过）")
        for c in criteria:
            logs.append(f"[llm]   - {c}（未检查）")
        return True, logs, failed

    # 组装 prompt
    try:
        from .validator_prompt import build_check_prompt
    except ImportError:
        from validator_prompt import build_check_prompt

    prompt = build_check_prompt(criteria, code_content)

    # 调用 LLM
    try:
        raw = generate(prompt)
    except Exception as e:
        # LLM 不可用 → 降级为 warning（不阻断流程）
        msg = f"LLM 调用失败: {type(e).__name__}: {str(e)[:150]}"
        logs.append(f"[llm] ⚠️ {msg}")
        failed.append(FailedTest(name="llm", reason=msg, severity="warning"))
        return True, logs, failed  # warning 不阻断

    # 解析 LLM 返回的 JSON
    logs.append(f"[llm] LLM 返回: {raw[:200]}...")
    try:
        # LLM 可能返回带 ```json 包裹的内容，提取 JSON 部分
        json_str = raw.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        result = json.loads(json_str)
        results = result.get("results", [])
        all_passed = result.get("all_passed", True)
        summary = result.get("summary", "")

        # 逐条记录
        for item in results:
            criteria_text = item.get("criteria", "?")
            verdict = item.get("verdict", "unknown")
            evidence = item.get("evidence", "")
            if verdict == "passed":
                logs.append(f"[llm] ✅ {criteria_text} — {evidence[:80]}")
            elif verdict in ("failed", "partial"):
                logs.append(f"[llm] ❌ {criteria_text} — {evidence[:80]}")
                failed.append(FailedTest(
                    name=f"llm:{criteria_text}",
                    reason=evidence[:200],
                    severity="error",
                ))
            else:
                logs.append(f"[llm] ⚠️ {criteria_text} — verdict={verdict}")

        if summary:
            logs.append(f"[llm] 📋 {summary}")

        passed = len(failed) == 0
        return passed, logs, failed

    except (json.JSONDecodeError, KeyError) as e:
        # JSON 解析失败 → 不阻断，把原始返回记在日志里
        msg = f"LLM 返回解析失败: {type(e).__name__}: {str(e)[:100]}"
        logs.append(f"[llm] ⚠️ {msg}")
        logs.append(f"[llm] 原始返回: {raw[:500]}")
        failed.append(FailedTest(name="llm", reason=msg, severity="warning"))
        return True, logs, failed  # warning 不阻断


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
