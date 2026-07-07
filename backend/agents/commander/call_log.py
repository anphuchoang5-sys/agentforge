"""
call_log.py — 调用记录（耗时+Token，供D展示）
同学A 产出物 · 对齐最终分工表"每次调用记录耗时和Token消耗"

所有模型调用经过此模块记录到 SQLite 日志表
D 的前端通过 API 读取这些数据展示指标图表
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


# 日志数据库路径（跟项目走）
LOG_DB_PATH = Path(__file__).parents[3] / "data" / "call_logs.db"


def _get_db() -> sqlite3.Connection:
    """获取日志数据库连接"""
    LOG_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(LOG_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            caller TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_preview TEXT,
            duration_ms INTEGER,
            tokens INTEGER,
            success INTEGER DEFAULT 1,
            error_msg TEXT
        )
    """)
    conn.commit()
    return conn


def log_call(
    caller: str,
    model: str,
    prompt: str,
    duration_ms: int,
    tokens: int = 0,
    success: bool = True,
    error_msg: Optional[str] = None,
):
    """记录一次模型调用

    参数:
        caller: 调用方标识，如 "commander", "backend_expert"
        model: 模型名称
        prompt: 完整提示词（只存前100字预览）
        duration_ms: 耗时（毫秒）
        tokens: 输出Token数
        success: 是否成功
        error_msg: 错误信息（失败时）
    """
    conn = _get_db()
    try:
        conn.execute(
            """
            INSERT INTO call_logs
                (timestamp, caller, model, prompt_preview, duration_ms, tokens, success, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                caller,
                model,
                prompt[:100],       # 只存预览，避免日志表太大
                duration_ms,
                tokens,
                1 if success else 0,
                error_msg,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_logs(limit: int = 50) -> list[dict]:
    """获取最近的调用记录（D的前端通过API调这个）"""
    conn = _get_db()
    try:
        cursor = conn.execute(
            "SELECT * FROM call_logs ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


