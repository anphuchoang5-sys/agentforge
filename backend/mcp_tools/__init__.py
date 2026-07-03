"""
mcp_tools — 同学C：桌面控制工具层

封装 pywinauto，提供 ui_click / ui_input / ui_get_text / screenshot / app_launch / app_close。
对齐 CLAUDE.md 目录结构 backend/mcp_tools/desktop_control.py。

使用方式:
    from backend.mcp_tools import launch_and_get_window, ui_input, screenshot
    win = launch_and_get_window("notepad.exe")
    ui_input(win, "Edit", "hello")
    img_b64 = screenshot(win)
"""

from .desktop_control import (
    app_launch,
    app_close,
    app_connect,
    ui_click,
    ui_input,
    ui_get_text,
    screenshot,
    launch_and_get_window,
)

__all__ = [
    "app_launch", "app_close", "app_connect",
    "ui_click", "ui_input", "ui_get_text",
    "screenshot", "launch_and_get_window",
]
