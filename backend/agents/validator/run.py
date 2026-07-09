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

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
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


# ===== UI 交互验证 =====

def _json_from_llm_response(raw: str) -> dict:
    """提取 LLM 返回中的 JSON 对象，兼容 ```json 包裹。"""
    json_str = raw.strip()
    if "```json" in json_str:
        json_str = json_str.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```", 1)[1].split("```", 1)[0].strip()
    return json.loads(json_str)


def _relative_rect(child_rect, window_rect):
    """把 pywinauto 屏幕绝对坐标转换成窗口截图内的相对坐标。"""
    return SimpleNamespace(
        left=max(0, child_rect.left - window_rect.left),
        top=max(0, child_rect.top - window_rect.top),
        right=max(0, child_rect.right - window_rect.left),
        bottom=max(0, child_rect.bottom - window_rect.top),
    )


def _region_changed(before_png_b64: str, after_png_b64: str, rect, threshold: float = 0.003) -> bool:
    """裁出 rect 区域，比较操作前后两张 base64 PNG 的像素差异比例。

    阈值取 0.3%（不是 2%）：真实测过一次"往空列表插入一条两字短文本"的场景，
    实际变化像素占比只有约 1.07%——列表控件通常面积很大，新增一行短文字占的
    像素比例天然很小，2% 的阈值会把这种最常见的场景直接判成"没变化"（问题
    是真实复现过的假阴性，不是猜测）。0.3% 留了安全边际，同时不会低到被
    单个反锯齿像素噪声触发。
    """
    import base64
    import io
    from PIL import Image, ImageChops

    before = Image.open(io.BytesIO(base64.b64decode(before_png_b64)))
    after = Image.open(io.BytesIO(base64.b64decode(after_png_b64)))
    width = min(before.width, after.width)
    height = min(before.height, after.height)
    box = (
        max(0, min(int(rect.left), width)),
        max(0, min(int(rect.top), height)),
        max(0, min(int(rect.right), width)),
        max(0, min(int(rect.bottom), height)),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return False

    crop_before = before.crop(box)
    crop_after = after.crop(box)
    if crop_before.size != crop_after.size:
        return True
    diff = ImageChops.difference(crop_before.convert("RGB"), crop_after.convert("RGB"))
    bbox = diff.getbbox()
    if bbox is None:
        return False
    diff_pixels = sum(1 for px in diff.getdata() if px != (0, 0, 0))
    total_pixels = crop_before.size[0] * crop_before.size[1]
    return (diff_pixels / total_pixels) > threshold if total_pixels else False


def _execute_interaction_plan(window, plan: dict, logs: List[str]) -> tuple[bool, str]:
    from backend.mcp_tools.desktop_control import (
        list_inputs,
        list_labels,
        list_output_widgets,
        list_buttons,
        click_widget,
        type_into_widget,
    )

    inputs = list_inputs(window)
    plan_inputs = plan.get("inputs_in_order", [])
    if len(inputs) < len(plan_inputs):
        return False, f"计划要填 {len(plan_inputs)} 个输入框，界面上只找到 {len(inputs)} 个"
    for widget, item in zip(inputs, plan_inputs):
        type_into_widget(widget, item.get("test_value", ""))

    output = plan.get("output_check", {})
    widget_type = output.get("widget_type")
    before_state = None
    target_widget = None
    if widget_type == "label":
        labels = list_labels(window)
        idx = output.get("widget_order_hint", 1) - 1
        if idx < 0 or idx >= len(labels):
            return False, f"widget_order_hint={idx + 1} 超出 Label 数量({len(labels)})"
        target_widget = labels[idx]
        before_state = target_widget.rectangle().width()
    elif widget_type == "treeview":
        widgets = list_output_widgets(window)
        if not widgets:
            return False, "没有找到列表/表格类控件"
        target_widget = widgets[0]
        before_state = screenshot(window)
    else:
        return False, f"未知的 widget_type: {widget_type!r}"

    buttons = list_buttons(window)
    order = plan.get("primary_action", {}).get("button_order_hint", 1)
    if order < 1 or order > len(buttons):
        return False, f"button_order_hint={order} 超出按钮数量({len(buttons)})"
    try:
        click_widget(buttons[order - 1])
    except Exception as e:
        return False, f"点击第{order}个按钮失败: {type(e).__name__}: {str(e)[:150]}"

    time.sleep(1)

    condition = output.get("success_condition", "")
    if widget_type == "label":
        after_state = target_widget.rectangle().width()
        if condition == "text_changes":
            ok = after_state != before_state
        elif condition == "text_non_empty":
            ok = after_state > 0
        else:
            return False, f"label 场景不支持 success_condition={condition!r}"
        logs.append(f"[ui_interact] label 宽度 操作前={before_state} 操作后={after_state}")
    else:
        after_state = screenshot(window)
        if condition != "row_count_increases":
            return False, f"treeview 场景不支持 success_condition={condition!r}"
        rel_rect = _relative_rect(target_widget.rectangle(), window.rectangle())
        ok = _region_changed(before_state, after_state, rel_rect)
        logs.append(f"[ui_interact] treeview 区域像素比对结果: {'有变化' if ok else '无变化'}")

    if not ok:
        return False, f"操作前后不满足 {condition}"
    return True, ""


def _ui_interaction_check(
    app_path: str,
    code_content: str,
    criteria_task_type: Optional[dict[str, str]],
    all_logs: List[str],
) -> List[FailedTest]:
    """生成并执行 UI 交互计划，返回 ui_validate 失败项。"""
    failed: List[FailedTest] = []
    task_types = set((criteria_task_type or {}).values())
    has_ui_criteria = bool(task_types.intersection({"ui_validate", "frontend"}))

    try:
        from backend.agents.commander.llm_client import generate_with_metrics
        from backend.agents.commander.call_log import log_call
    except ImportError as e:
        msg = f"UI 交互计划依赖导入失败: {type(e).__name__}: {str(e)[:150]}"
        all_logs.append(f"[ui_interact] ❌ {msg}")
        if has_ui_criteria:
            failed.append(FailedTest(name="ui_interact", reason=msg, task_type="ui_validate", severity="error"))
        return failed
    try:
        from .validator_prompt import build_interaction_plan_prompt
    except ImportError as exc:
        if "attempted relative import" not in str(exc):
            raise
        from validator_prompt import build_interaction_plan_prompt

    retry_feedback = ""
    last_error = ""
    last_plan = None
    for attempt in range(1, 4):
        prompt = build_interaction_plan_prompt(code_content or "", retry_feedback=retry_feedback)
        start = time.time()
        try:
            metrics = generate_with_metrics(prompt)
            raw = metrics["response"]
            log_call(
                caller="validator_ui_interact",
                model=metrics["model"],
                prompt=prompt[:100],
                duration_ms=metrics["duration_ms"],
                tokens=metrics["tokens"],
                success=True,
            )
        except Exception as e:
            msg = f"UI 交互计划 LLM 调用失败: {type(e).__name__}: {str(e)[:150]}"
            all_logs.append(f"[ui_interact] ❌ {msg}")
            log_call(
                caller="validator_ui_interact",
                model="unknown",
                prompt=prompt[:100],
                duration_ms=round((time.time() - start) * 1000),
                tokens=0,
                success=False,
                error_msg=str(e)[:200],
            )
            failed.append(FailedTest(name="ui_interact", reason=msg, task_type="ui_validate", severity="error"))
            return failed

        all_logs.append(f"[ui_interact] LLM 返回: {raw[:200]}...")
        try:
            plan = _json_from_llm_response(raw)
        except (json.JSONDecodeError, IndexError) as e:
            msg = f"UI 交互计划 JSON 解析失败: {type(e).__name__}: {str(e)[:100]}"
            all_logs.append(f"[ui_interact] ❌ {msg}")
            failed.append(FailedTest(name="ui_interact", reason=msg, task_type="ui_validate", severity="error"))
            return failed

        last_plan = plan
        all_logs.append(f"[ui_interact] plan: {json.dumps(plan, ensure_ascii=False)}")
        if plan.get("applicable") is False:
            reason = plan.get("reason_if_not_applicable", "LLM 判定没有可自动化的 UI 交互")
            if has_ui_criteria:
                msg = f"存在 frontend/ui_validate 验收标准，但交互计划不适用: {reason}"
                all_logs.append(f"[ui_interact] ❌ {msg}")
                failed.append(FailedTest(name="ui_interact", reason=msg, task_type="ui_validate", severity="error"))
            else:
                all_logs.append(f"[ui_interact] ⏭️ 不适用: {reason}")
            return failed

        app = None
        proc = None
        connected_pid = None
        try:
            window, app, proc, connected_pid = _launch_app(app_path, all_logs)
            ok, error = _execute_interaction_plan(window, plan, all_logs)
        except Exception as e:
            ok = False
            error = f"UI 交互执行异常: {type(e).__name__}: {str(e)[:150]}"
        finally:
            _cleanup_app(app, proc, connected_pid)

        if ok:
            all_logs.append("[ui_interact] ✅ 交互计划执行通过")
            return failed

        last_error = error
        all_logs.append(f"[ui_interact] ❌ 第 {attempt} 次执行失败: {error}")
        if attempt < 3 and ("填" in error or "值" in error):
            retry_feedback = error
            all_logs.append("[ui_interact] 根据输入值相关失败反馈重试生成计划")
            continue
        break

    reason = last_error or f"UI 交互计划执行失败: {last_plan}"
    failed.append(FailedTest(name="ui_interact", reason=reason, task_type="ui_validate", severity="error"))
    return failed


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

    # 5. UI 交互验证（独立启动一次应用，不与截图共享进程）
    if compile_ok and app_type == "desktop":
        if code_content is None:
            app_dir = str(Path(app_path).parent) if Path(app_path).is_file() else app_path
            code_content = checkers.read_app_code(app_dir)
        all_failed.extend(_ui_interaction_check(app_path, code_content, criteria_task_type, all_logs))
    elif compile_ok and app_type != "desktop":
        all_logs.append("[ui_interact] ⏭️ 非桌面 Tk 应用，跳过 UI 交互验证")
    else:
        all_logs.append("[ui_interact] ⏭️ 编译未通过，跳过 UI 交互验证")

    # 6. 桌面应用截图（只有编译通过 + 桌面应用才启动）
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

    # 7. 汇总结论
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
