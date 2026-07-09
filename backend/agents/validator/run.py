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
except ImportError as exc:
    if "attempted relative import" not in str(exc):
        raise
    from schemas import TestReport, FailedTest
    import checkers

# desktop_control 在 backend/mcp_tools/，双导入
try:
    from backend.mcp_tools.desktop_control import screenshot
    from backend.tools.console_encoding import ensure_utf8_console
except ImportError as exc:
    if "No module named 'backend'" not in str(exc):
        raise
    # 直接运行时回退：把项目根加入 sys.path，让 backend namespace package 可导入
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parents[3]))
    from backend.mcp_tools.desktop_control import screenshot
    from backend.tools.console_encoding import ensure_utf8_console

# 自测块（__main__）里会 print(report.logs)，里面全是 ✅❌⚠️⏭️ 前缀，
# Windows 默认 GBK 控制台直接打印会崩溃（problem.md 第31条同一类问题，
# 这里补上；被 B 的 run.py import 时也会调，重复调用无副作用）。
ensure_utf8_console()


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

def _descendant_pids(root_pid: int) -> List[int]:
    """枚举 root_pid 的所有子孙进程 PID（Win32 Toolhelp32 快照，不依赖 psutil）

    .venv 里的 pythonw.exe 在部分 CPython 发行版（venvlauncher 机制）不是解释器本体，
    而是一个转发桩：Popen 拿到的 PID 是这个桩进程，它再拉起真正的解释器子进程，
    Tkinter 窗口是子进程创建的，归属于子进程 PID，不归属于桩进程 PID。
    Application.connect(process=桩PID) 永远找不到窗口（"No windows for that
    process could be found"），必须连子进程 PID 才行。
    """
    import ctypes
    from ctypes import wintypes

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", ctypes.c_wchar * 260),
        ]

    TH32CS_SNAPPROCESS = 0x00000002
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == -1:
        return []

    parent_map: dict[int, List[int]] = {}
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if kernel32.Process32FirstW(snapshot, ctypes.byref(entry)):
            while True:
                parent_map.setdefault(entry.th32ParentProcessID, []).append(entry.th32ProcessID)
                if not kernel32.Process32NextW(snapshot, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snapshot)

    descendants: List[int] = []
    frontier = [root_pid]
    while frontier:
        pid = frontier.pop()
        children = parent_map.get(pid, [])
        descendants.extend(children)
        frontier.extend(children)
    return descendants


def _launch_app(app_path: str, logs: List[str]):
    """启动桌面应用并返回 window/app/proc/connected_pid

    用 subprocess 启动 + Application.connect(process=pid) 连接（最鲁棒）:
    - 不依赖 pywinauto 的 start 进程跟踪（对 pythonw 不可靠）
    - 只连目标进程 + 其子孙进程，不枚举全部窗口（避免 sandbox 限制）
    """
    app_path_obj = Path(app_path)
    if not app_path_obj.exists():
        raise FileNotFoundError(f"应用文件不存在: {app_path}")

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
    connected_pid = None
    try:
        proc = _sp.Popen(
            [launcher, app_path],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            cwd=str(app_path_obj.parent),
        )
        logs.append(f"[screenshot] 子进程 PID={proc.pid}，等待窗口渲染...")

        # 轮询等窗口出现（Tkinter 渲染可能延迟 3-9 秒）
        # backend=win32：Tkinter/标准 Win32 GUI 必须 win32（uia 下 top_window 返回空）
        window = None
        for wait_s in [3, 2, 2, 2]:  # 最多累计 9 秒
            _time.sleep(wait_s)
            if proc.poll() is not None:
                raise RuntimeError(f"子进程已退出（returncode={proc.returncode}），可能启动失败")
            # 候选 PID：先试桩进程自己，再试它的子孙进程（venvlauncher 场景）
            for candidate_pid in [proc.pid] + _descendant_pids(proc.pid):
                try:
                    app = _App(backend="win32").connect(process=candidate_pid, timeout=3)
                    visible_windows = []
                    for candidate_window in app.windows(visible_only=True):
                        rect = candidate_window.rectangle()
                        if rect.width() >= 100 and rect.height() >= 80:
                            visible_windows.append(candidate_window)
                    window = visible_windows[0] if visible_windows else app.top_window()
                    rect = window.rectangle()
                    if window.is_visible() and rect.width() >= 100 and rect.height() >= 80:
                        connected_pid = candidate_pid
                        logs.append(
                            f"[screenshot] 窗口已就绪（PID={candidate_pid}）: "
                            f"{window.window_text()!r} class={window.class_name()!r} rect={rect}"
                        )
                        break
                except Exception as retry_e:
                    logs.append(f"[screenshot] 重试中(PID={candidate_pid}): {type(retry_e).__name__}: {str(retry_e)[:100]}")
                    app = None
                    window = None
            if window is not None:
                break

        if window is None:
            raise RuntimeError("等待窗口超时（9 秒内未出现可见窗口）")

        return window, app, proc, connected_pid
    except Exception:
        _cleanup_app(app, proc, connected_pid)
        raise


def _cleanup_app(app, proc, connected_pid) -> None:
    """清理 pywinauto 连接到的 GUI 进程和启动器进程。"""
    import subprocess as _sp

    if app is not None:
        try:
            app.kill()
        except Exception:
            pass
    if proc is not None:
        candidate_pids = [proc.pid] + _descendant_pids(proc.pid)
        for pid in candidate_pids:
            if pid == connected_pid:
                continue
            try:
                _sp.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
            except Exception:
                pass


def _launch_and_screenshot(app_path: str, logs: List[str]) -> tuple[str, Optional[str]]:
    """启动桌面应用并截图

    返回:
        (screenshot_b64, executable_name) — 截图失败时 screenshot_b64 为空
    """
    app = None
    proc = None
    connected_pid = None
    try:
        window, app, proc, connected_pid = _launch_app(app_path, logs)
        img_b64 = screenshot(window)
        logs.append(f"[screenshot] ✅ 截图成功（{len(img_b64)} 字符 base64）")
        launcher = proc.args[0] if proc is not None and getattr(proc, "args", None) else None
        return img_b64, launcher
    except Exception as e:
        import traceback as _tb
        logs.append(f"[screenshot] ⚠️ 启动/截图失败: {type(e).__name__}: {str(e)[:200]}")
        logs.append(f"[screenshot] traceback: {_tb.format_exc().splitlines()[-1][:200]}")
        return "", None
    finally:
        _cleanup_app(app, proc, connected_pid)


# ===== 主入口 =====

def validate(
    app_path: str,
    criteria: Optional[List[str]] = None,
    criteria_task_type: Optional[dict[str, str]] = None,
    iteration: int = 0,
    code_content: Optional[str] = None,
    pytest_result_path: Optional[str] = None,
) -> TestReport:
    """验证者主入口：对外接口实现

    参数:
        app_path: 应用入口文件路径，如 "./output/todo_app/main.py"
        criteria: 验收标准列表（来自 Commander，可选；MVP 阶段第④项为桩）
        iteration: 修复轮次（由 B 传入，记录在报告里供 D 展示）
        code_content: 可选，调用方直接提供的代码内容（如 B 的 ProjectState 里
            backend_code/frontend_code/test_code 拼接后的完整未截断字符串）。
            传了就直接用，不用再从硬盘读取+截断，避免 read_app_code() 的
            8000 字符上限把长文件（尤其 test_app.py）切掉
        pytest_result_path: 可选，B 的 TestExpert 用 `pytest --json-report`
            生成的 JSON 报告文件路径。传了就读取真实测试结果，不传则
            pytest_check 保持跳过（向后兼容，不影响独立自测）

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
    # detect_app_type()/read_app_code() 内部该抛的抛（路径为空/不存在时 raise），
    # 这符合"内部检查该报错就报错"的原则；但 validate() 自己的文档承诺是"总是
    # 返回 TestReport"——如果这里不接住，紧接着 compile_check() 对同一种
    # "路径不存在"情况本来准备好的优雅处理（返回失败而不是崩）根本没机会跑到，
    # 整个函数会在这里直接崩给调用方一个未处理异常，把 validator_node 的重试
    # 闭环也一起干掉。这里接住，转换成跟 compile_check 一致的"记一条失败，继续走"
    try:
        app_type = detect_app_type(app_path)
    except (ValueError, FileNotFoundError) as e:
        app_type = "unknown"
        all_logs.append(f"[detect] ❌ {e}")
        all_failed.append(FailedTest(name="detect", reason=str(e), severity="error"))
    else:
        all_logs.append(f"[detect] 应用类型: {app_type}")
        if app_type == "unknown":
            msg = "无法识别应用类型，不能证明生成了可运行 UI"
            all_logs.append(f"[detect] ❌ {msg}")
            all_failed.append(FailedTest(name="detect", reason=msg, severity="error"))

    # 1. 编译检查
    passed, logs, failed = checkers.compile_check(app_path)
    all_logs.extend(logs)
    all_failed.extend(failed)
    compile_ok = passed

    # 2. ruff 静态检查
    passed, logs, failed = checkers.ruff_check(app_path)
    all_logs.extend(logs)
    all_failed.extend(failed)

    # 3. pytest 检查（有 pytest_result_path 就读真实结果，没有就跳过）
    passed, logs, failed = checkers.pytest_check(app_path, pytest_result_path)
    all_logs.extend(logs)
    all_failed.extend(failed)

    # 4. LLM 验收标准核对
    # 优先用调用方直接提供的 code_content（完整未截断）；
    # 没提供才退回读取整个项目目录（db.py/app.py/test_app.py 拼一起，会截断）
    if code_content is None and criteria:
        app_dir = str(Path(app_path).parent) if Path(app_path).is_file() else app_path
        code_content = checkers.read_app_code(app_dir)
    passed, logs, failed = checkers.llm_check(
        app_path,
        criteria,
        code_content,
        criteria_task_type=criteria_task_type,
    )
    all_logs.extend(logs)
    all_failed.extend(failed)

    # 5. 桌面应用截图（只有编译通过 + 桌面应用才启动）
    screenshot_b64 = ""
    if compile_ok and app_type == "desktop":
        screenshot_b64, _ = _launch_and_screenshot(app_path, all_logs)
        if not screenshot_b64:
            msg = "桌面应用启动或截图失败，不能把 UI 验证视为通过"
            all_logs.append(f"[screenshot] ❌ {msg}")
            all_failed.append(FailedTest(name="screenshot", reason=msg, severity="error"))
    elif compile_ok and app_type == "web":
        msg = "Web 应用验证未集成 Playwright，不能跳过后视为通过"
        all_logs.append(f"[screenshot] ❌ {msg}")
        all_failed.append(FailedTest(name="screenshot", reason=msg, severity="error"))
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
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        status["ruff"] = result.returncode == 0
    except subprocess.TimeoutExpired:
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
