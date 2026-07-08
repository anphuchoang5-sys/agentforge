"""
desktop_control.py — pywinauto 桌面控制封装
同学C 核心产出物 · 对齐分工表 ui_click/ui_input/ui_get_text/screenshot/app_launch/app_close

设计原则（对齐 CLAUDE.md）:
- 走 Win32 Accessibility API（backend="uia"），不依赖坐标
- 元素定位多策略兜底：best_match → auto_id → control_type
- 所有函数返回值可序列化（截图返回 base64 字符串，不返回 PIL 对象）

独立验证方式（对齐分工表）:
    用记事本/计算器做目标，验证能否找到按钮、点击、截图
"""

import base64
import io

from pywinauto import Application
from pywinauto.findwindows import ElementNotFoundError


# ===== 启动 / 关闭 =====

def app_launch(
    executable: str,
    timeout: float = 10,
    wait_for_idle: bool = False,
    backend: str = "win32",
) -> Application:
    """启动应用

    参数:
        executable: 可执行文件名或路径，如 "notepad.exe" / "calc.exe" / 'python "app.py"'
        timeout: 等待窗口出现的秒数
        wait_for_idle: 是否等待进程 WaitForInputIdle（GUI 进程如记事本可设 True；
            用 python.exe 启动 GUI 应用必须 False，否则报错 1471「不是 GUI 进程」）
        backend: pywinauto 后端，"win32"（默认，Tkinter/记事本/计算器友好）
            或 "uia"（现代 WPF/UWP 应用用）。Tkinter 必须 win32，uia 下 top_window 返回空。
    返回:
        Application 对象（后续 ui_* 函数要传它）
    """
    app = Application(backend=backend).start(
        executable, timeout=timeout, wait_for_idle=wait_for_idle
    )
    # 等主窗口出现（start 不等 idle 时，靠这里轮询窗口可见）
    app.top_window().wait("visible", timeout=timeout)
    return app


# ===== 元素定位（内部） =====

def _find(window, locator: str):
    """多策略元素定位

    locator 优先级:
        1. best_match   — 最常用，如 "Edit" / "确定" / "OK"
        2. auto_id      — 控件自动化 ID
        3. control_type — 控件类型，如 "Button" / "Edit"
        4. title        — 控件标题

    任一策略命中即返回。
    """
    errors = []

    # 1. best_match
    try:
        return window.child_window(best_match=locator)
    except Exception as e:
        errors.append(f"best_match={locator}: {e}")

    # 2. auto_id
    try:
        return window.child_window(auto_id=locator)
    except Exception as e:
        errors.append(f"auto_id={locator}: {e}")

    # 3. control_type
    try:
        return window.child_window(control_type=locator)
    except Exception as e:
        errors.append(f"control_type={locator}: {e}")

    # 4. title
    try:
        return window.child_window(title=locator)
    except Exception as e:
        errors.append(f"title={locator}: {e}")

    raise ElementNotFoundError(
        f"找不到元素 '{locator}'，已尝试 best_match/auto_id/control_type/title\n"
        + "\n".join(errors)
    )


def _resolve_window(app_or_window):
    """统一处理传入参数：Application 取 top_window，WindowSpecification 直接返回

    注意：不能用 hasattr(window, "top_window") 判断，因为 WindowSpecification
    的 __getattr__ 是动态的，hasattr 永远返回 True，会误把窗口当 Application
    再调一次 top_window()（被解析成找名为 "top_window" 的子控件 → 报错）。
    用 isinstance(Application) 精确判断。
    """
    if isinstance(app_or_window, Application):
        return app_or_window.top_window()
    return app_or_window


def _sort_by_position(widgets: list) -> list:
    """按屏幕坐标从上到下、同行从左到右排序。

    pywinauto 的 descendants() 返回顺序取决于 Win32 子窗口枚举顺序（Z-order），
    实测与 Tkinter 代码里 .pack() 的创建顺序相反（最后创建的控件排最前）。
    LLM 生成测试计划时是按源码从上到下阅读来判断"第几个控件"，只有按屏幕
    坐标重新排序才能让 order_hint 和实际控件对上。
    """
    return sorted(widgets, key=lambda w: (w.rectangle().top, w.rectangle().left))


def list_inputs(window) -> list:
    """按视觉从上到下顺序返回窗口里所有输入框控件（TkChild 类，高度 < 40px）"""
    window = _resolve_window(window)
    candidates = window.descendants(class_name="TkChild")
    return _sort_by_position([c for c in candidates if c.rectangle().height() < 40])


def list_labels(window) -> list:
    """按视觉从上到下顺序返回窗口里所有 Label 控件"""
    window = _resolve_window(window)
    return _sort_by_position(window.descendants(class_name="Static"))


def list_output_widgets(window) -> list:
    """按视觉从上到下顺序返回窗口里所有列表/表格类控件（TkChild 类，高度 >= 40px）"""
    window = _resolve_window(window)
    candidates = window.descendants(class_name="TkChild")
    result = []
    for candidate in candidates:
        if candidate.rectangle().height() < 40:
            continue
        nested = candidate.descendants(class_name="TkChild")
        if nested:
            continue
        result.append(candidate)
    return _sort_by_position(result)


def list_buttons(window) -> list:
    """按视觉从上到下顺序返回窗口里所有按钮控件"""
    window = _resolve_window(window)
    return _sort_by_position(window.descendants(class_name="Button"))


def click_widget(widget) -> None:
    """对已经定位好的控件对象做真实点击（click_input，不是 .click()）"""
    widget.click_input()


def type_into_widget(widget, text: str) -> None:
    """对已经定位好的控件对象敲入文字（click_input 聚焦 + type_keys 输入）"""
    widget.click_input()
    widget.type_keys(text, with_spaces=True)


# ===== UI 操作 =====

def ui_click(app_or_window, locator: str, timeout: float = 5) -> None:
    """点击指定元素（按钮/菜单等）

    参数:
        app_or_window: Application 对象 或 窗口对象
        locator: 元素定位符，如 "确定" / "Add" / "Button"
    """
    window = _resolve_window(app_or_window)
    elem = _find(window, locator)
    elem.wait("enabled visible", timeout=timeout)
    try:
        elem.click_input()
        return
    except Exception:
        pass
    elem.click()


def ui_input(app_or_window, locator: str, text: str, timeout: float = 5) -> None:
    """向输入框填入文字

    优先用 set_text（直接设值，支持中文/特殊字符）；
    不支持 set_text 时回退剪贴板粘贴（Ctrl+A → Ctrl+V）；
    最后兜底 type_keys（仅纯 ASCII 场景可靠）。
    """
    window = _resolve_window(app_or_window)
    elem = _find(window, locator)
    elem.wait("enabled visible", timeout=timeout)
    try:
        elem.click_input()
    except Exception:
        elem.set_focus()

    # 策略1：set_text（直接赋值，不经过键盘模拟，中文/特殊字符安全）
    try:
        elem.set_text(text)
        return
    except Exception:
        pass  # 某些控件不支持 set_text，继续下一策略

    # 策略2：剪贴板粘贴（Ctrl+A 全选 → Ctrl+V 粘贴）
    try:
        import pywinauto.clipboard as _clip
        _clip.SetClipboardData(text)
        elem.click_input()
        elem.type_keys("^a{BACKSPACE}", with_spaces=True)
        elem.type_keys("^v", with_spaces=True)
        return
    except Exception:
        pass  # 剪贴板可能被占用，继续兜底

    # 策略3：type_keys 兜底（仅纯 ASCII 可靠）
    elem.click_input()
    elem.type_keys("^a{BACKSPACE}", with_spaces=True)
    elem.type_keys(text, with_spaces=True)


def ui_get_text(app_or_window, locator: str, timeout: float = 5) -> str:
    """读取元素文字内容

    返回:
        元素的文字（Edit 返回文本，Button 返回标题，List 返回选中项等）
    """
    window = _resolve_window(app_or_window)
    elem = _find(window, locator)
    elem.wait("enabled visible", timeout=timeout)

    # 不同控件取文本方式不同，逐个尝试
    for attr in ("window_text", "get_value", "texts"):
        try:
            val = getattr(elem, attr)
            result = val() if callable(val) else val
            if isinstance(result, list):
                result = "\n".join(result)
            if result:
                return str(result).strip()
        except Exception:
            continue
    return ""


# ===== 截图 =====

def screenshot(app_or_window=None) -> str:
    """截取窗口截图，返回 base64 PNG（不带 data: 前缀）

    参数:
        app_or_window: None=全屏截图；Application/窗口对象=指定窗口
    返回:
        base64 编码的 PNG 字符串
    """
    if app_or_window is None:
        # 全屏截图（兜底，当窗口截图失败时用）
        from PIL import ImageGrab
        img = ImageGrab.grab()
    else:
        window = _resolve_window(app_or_window)
        # capture_as_image() 不是从窗口离屏绘制缓冲区取图，而是直接截取窗口
        # 在屏幕上的那块像素区域（pywinauto 官方已知限制/issue #995）——如果
        # 这块屏幕区域被别的窗口挡住，截到的会是挡在上面的窗口内容，不是目标
        # 应用真正的画面。截图前先把目标窗口切到最前面/给焦点，避免被其他
        # 窗口遮挡导致截图内容驴唇不对马嘴
        try:
            window.set_focus()
        except Exception as e:
            # 不能吞得完全无声：set_focus 失败意味着截图可能被遮挡窗口覆盖
            # （problem_passed.md #50 的原始 bug），这里只是不让它中断截图流程，
            # 但必须留下可见痕迹，否则会静默复现 #50。
            import sys as _sys
            print(f"[screenshot] ⚠️ set_focus 失败，截图可能被遮挡: {type(e).__name__}: {e}", file=_sys.stderr)
        img = window.capture_as_image()

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
