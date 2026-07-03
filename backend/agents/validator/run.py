"""
run.py — 验证者 Agent 入口
同学C 核心产出物 · 对外接口实现

对外接口（B 调用 / D 展示）:
    from backend.agents.validator import validate
    report = validate("./output/todo_app/main.py")
    # report.passed / report.logs / report.screenshot / report.failed_tests
    # report.model_dump() → 接口 JSON

可选传入验收标准（来自 Commander 的 TaskDecomposition.tasks[].acceptance_criteria）:
    report = validate(app_path, criteria=["支持添加任务", "支持删除任务"])
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# 双导入（对齐 A 的 decompose.py 风格）
try:
    from .schemas import TestReport, FailedTest
    from . import checkers
except ImportError:
    from schemas import TestReport, FailedTest
    import checkers

# desktop_control 在 backend/mcp_tools/，双导入
try:
    from backend.mcp_tools.desktop_control import (
        app_launch, app_close, ui_click, ui_input, ui_get_text, screenshot,
        launch_and_get_window,
    )
except ImportError:
    # 直接运行时回退：把项目根加入 sys.path，让 backend namespace package 可导入
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parents[3]))
    from backend.mcp_tools.desktop_control import (
        app_launch, app_close, ui_click, ui_input, ui_get_text, screenshot,
        launch_and_get_window,
    )


# ===== 应用类型探测 =====

def detect_app_type(app_path: str) -> str:
    """探测应用类型（不扩展接口，自动从代码内容判断）

    返回:
        "desktop" — Tkinter / PyQt / wxPython（走 pywinauto）
        "web"     — Flask / FastAPI / Django（走 Playwright，MVP 暂不支持）
        "unknown" — 无法判断
    """
    code = checkers.read_app_code(app_path, max_chars=20000)

    # 桌面框架特征
    desktop_patterns = [r"\bimport\s+tkinter\b", r"\bfrom\s+tkinter\b",
                        r"\bimport\s+PyQt", r"\bfrom\s+PyQt",
                        r"\bimport\s+wx\b", r"\bfrom\s+wx\b"]
    if any(re.search(p, code) for p in desktop_patterns):
        return "desktop"

    # Web 框架特征
    web_patterns = [r"\bfrom\s+flask\b", r"\bimport\s+flask\b",
                    r"\bfrom\s+fastapi\b", r"\bimport\s+fastapi\b",
                    r"\bfrom\s+django\b", r"\bimport\s+django\b",
                    r"\bimport\s+uvicorn\b"]
    if any(re.search(p, code) for p in web_patterns):
        return "web"

    return "unknown"


# ===== 桌面应用启动 + 截图 =====

def _launch_and_screenshot(app_path: str, logs: List[str]) -> tuple[str, Optional[str]]:
    """启动桌面应用并截图

    用 subprocess 启动 + Application.connect(process=pid) 连接（最鲁棒）:
    - 不依赖 pywinauto 的 start 进程跟踪（对 pythonw 不可靠）
    - 只连目标进程，不枚举所有窗口（避免 sandbox 限制）

    返回:
        (screenshot_b64, executable_name) — 截图失败时 screenshot_b64 为空
    """
    app_path_obj = Path(app_path)
    if not app_path_obj.exists():
        logs.append(f"[screenshot] ⏭️ 应用文件不存在，跳过启动截图: {app_path}")
        return "", None

    import sys as _sys
    import subprocess as _sp
    import time as _time
    from pywinauto import Application as _App

    # 优先 pythonw（无控制台窗口，截图更干净），回退 python
    pyw = _sys.executable.replace("python.exe", "pythonw.exe")
    launcher = pyw if Path(pyw).exists() else _sys.executable
    logs.append(f"[screenshot] 启动: {launcher} {app_path}")

    proc = None
    app = None
    try:
        proc = _sp.Popen([launcher, app_path], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        logs.append(f"[screenshot] 子进程 PID={proc.pid}，等待窗口渲染...")

        # 轮询等窗口出现（Tkinter 渲染可能延迟 3-9 秒）
        # backend=win32：Tkinter/标准 Win32 GUI 必须 win32（uia 下 top_window 返回空）
        window = None
        for wait_s in [3, 2, 2, 2]:  # 最多累计 9 秒
            _time.sleep(wait_s)
            if proc.poll() is not None:
                raise RuntimeError(f"子进程已退出（returncode={proc.returncode}），可能启动失败")
            try:
                app = _App(backend="win32").connect(process=proc.pid, timeout=3)
                window = app.top_window()
                if window.exists() and window.is_visible():
                    logs.append(f"[screenshot] 窗口已就绪: {window.window_text()!r}")
                    break
            except Exception as retry_e:
                logs.append(f"[screenshot] 重试中: {type(retry_e).__name__}: {str(retry_e)[:100]}")
                app = None
                window = None

        if window is None:
            raise RuntimeError("等待窗口超时（9 秒内未出现可见窗口）")

        img_b64 = screenshot(window)
        logs.append(f"[screenshot] ✅ 截图成功（{len(img_b64)} 字符 base64）")
        return img_b64, launcher
    except Exception as e:
        import traceback as _tb
        logs.append(f"[screenshot] ⚠️ 启动/截图失败: {type(e).__name__}: {str(e)[:200]}")
        logs.append(f"[screenshot] traceback: {_tb.format_exc().splitlines()[-1][:200]}")
        # 截图失败不阻断，返回空截图
        return "", None
    finally:
        # 清理进程：优先 kill app，兜底 kill proc
        if app is not None:
            try:
                app.kill()
            except Exception:
                pass
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


# ===== 主入口 =====

def validate(
    app_path: str,
    criteria: Optional[List[str]] = None,
    iteration: int = 0,
) -> TestReport:
    """验证者主入口：对外接口实现

    参数:
        app_path: 应用入口文件路径，如 "./output/todo_app/main.py"
        criteria: 验收标准列表（来自 Commander，可选；MVP 阶段第④项为桩）
        iteration: 修复轮次（由 B 传入，记录在报告里供 D 展示）

    返回:
        TestReport — Pydantic 对象，.model_dump() 即接口 JSON

    B 调用示例:
        from backend.agents.validator import validate
        report = validate("./output/todo_app/main.py", criteria=["支持添加任务"])
        if not report.passed:
            # 触发 fix_expert 修复
            ...
    """
    all_logs: List[str] = [f"{'='*50}", f"验证开始: {app_path}", f"{'='*50}"]
    all_failed: List[FailedTest] = []

    # 0. 探测应用类型
    app_type = detect_app_type(app_path)
    all_logs.append(f"[detect] 应用类型: {app_type}")

    # 1. 编译检查
    passed, logs, failed = checkers.compile_check(app_path)
    all_logs.extend(logs)
    all_failed.extend(failed)
    compile_ok = passed

    # 2. ruff 静态检查
    passed, logs, failed = checkers.ruff_check(app_path)
    all_logs.extend(logs)
    all_failed.extend(failed)

    # 3. pytest 检查（桩）
    passed, logs, failed = checkers.pytest_check(app_path)
    all_logs.extend(logs)
    all_failed.extend(failed)

    # 4. LLM 验收标准核对（桩）
    code_content = checkers.read_app_code(app_path) if criteria else None
    passed, logs, failed = checkers.llm_check(app_path, criteria, code_content)
    all_logs.extend(logs)
    all_failed.extend(failed)

    # 5. 桌面应用截图（只有编译通过 + 桌面应用才启动）
    screenshot_b64 = ""
    if compile_ok and app_type == "desktop":
        screenshot_b64, _ = _launch_and_screenshot(app_path, all_logs)
    elif compile_ok and app_type == "web":
        all_logs.append("[screenshot] ⏭️ Web 应用暂不支持（Playwright 未集成），跳过截图")
    elif not compile_ok:
        all_logs.append("[screenshot] ⏭️ 编译未通过，跳过启动截图")

    # 6. 汇总结论
    # severity=error 的失败项 → passed=False
    blocking_failures = [f for f in all_failed if f.severity == "error"]
    passed = len(blocking_failures) == 0

    all_logs.append(f"{'='*50}")
    if passed:
        all_logs.append(f"✅ 验证通过（{len(all_failed)} 个 warning，无 error）")
    else:
        all_logs.append(f"❌ 验证失败（{len(blocking_failures)} 个 error）")

    return TestReport(
        passed=passed,
        logs=all_logs,
        screenshot=screenshot_b64,
        failed_tests=all_failed,
        app_path=app_path,
        app_type=app_type,
        iteration=iteration,
    )


# ===== 健康检查（供 D 探活 / B 联调前自检） =====

def health_check() -> dict:
    """检查 validator 依赖是否就绪"""
    status = {"pywinauto": False, "ruff": False, "py_compile": True}
    try:
        import pywinauto
        status["pywinauto"] = True
    except ImportError:
        pass
    try:
        subprocess.run(["ruff", "--version"], capture_output=True, timeout=5)
        status["ruff"] = True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return status


# ===== 自测 =====
if __name__ == "__main__":
    # 造一个最小 Tkinter 应用做端到端验证
    import tempfile
    demo_code = '''import tkinter as tk

root = tk.Tk()
root.title("Demo Todo")
root.geometry("300x200")

entry = tk.Entry(root)
entry.pack(pady=5)

def add_task():
    listbox.insert(tk.END, entry.get())
    entry.delete(0, tk.END)

btn = tk.Button(root, text="Add", command=add_task)
btn.pack()

listbox = tk.Listbox(root)
listbox.pack(pady=5)

root.mainloop()
'''
    demo_path = Path(tempfile.gettempdir()) / "validator_demo_tk.py"
    demo_path.write_text(demo_code, encoding="utf-8")

    print("=== 健康检查 ===")
    print(health_check())

    print("\n=== 验证 Tkinter Demo ===")
    report = validate(
        str(demo_path),
        criteria=["添加任务按钮", "任务列表显示"],
        iteration=1,
    )
    print(f"\npassed: {report.passed}")
    print(f"app_type: {report.app_type}")
    print(f"failed_tests: {len(report.failed_tests)}")
    print(f"screenshot: {'有' if report.screenshot else '无'} ({len(report.screenshot)} 字符)")
    print("\n--- 日志 ---")
    for log in report.logs:
        print(log)
