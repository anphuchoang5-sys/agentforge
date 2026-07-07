"""
mcp_tools — 同学C：桌面控制工具层

封装 pywinauto，提供 ui_click / ui_input / ui_get_text / screenshot / app_launch。
对齐 CLAUDE.md 目录结构 backend/mcp_tools/desktop_control.py。

使用方式:
    from backend.mcp_tools import app_launch, ui_input, screenshot
    app = app_launch("notepad.exe")
    ui_input(app, "Edit", "hello")
    img_b64 = screenshot(app)
"""

from .desktop_control import (
    app_launch,
    ui_click,
    ui_input,
    ui_get_text,
    screenshot,
)

__all__ = [
    "app_launch",
    "ui_click", "ui_input", "ui_get_text",
    "screenshot",
]
