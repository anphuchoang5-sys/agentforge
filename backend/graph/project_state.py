"""
project_state.py — 所有 Agent 共享的「大白板」
B 定义，全组遵守

LangGraph 在每个节点之间传递这个 dict。
每个 Agent 只读/写自己负责的字段。
"""

from typing import TypedDict, Optional, List
from backend.agents.commander.schemas import TaskDecomposition


class ProjectState(TypedDict):
    # ── Commander（A）写 ────────────────────────
    user_input: str                          # 用户原始需求
    task_decomposition: Optional[TaskDecomposition]  # 拆解结果

    # ── BackendExpert 写 ────────────────────────
    backend_code: Optional[str]              # 生成的后端代码内容
    backend_path: Optional[str]             # 落盘路径，如 ./output/generated_app/db.py

    # ── FrontendExpert 写 ───────────────────────
    frontend_code: Optional[str]
    frontend_path: Optional[str]

    # ── TestExpert 写 ───────────────────────────
    test_code: Optional[str]
    test_path: Optional[str]
    test_results: Optional[str]             # "5 passed, 0 failed"
    test_passed: Optional[bool]
    pytest_report_path: Optional[str]       # pytest --json-report 生成的 JSON 报告路径，供 C 的 pytest_check 读取

    # ── Validator（C）写 ────────────────────────
    validation_passed: Optional[bool]
    validation_logs: Optional[List[str]]
    screenshot_path: Optional[str]

    # ── 流程控制（B 维护）──────────────────────
    iteration_count: int                    # 当前重试轮数，超 5 次强制终止
    output_base_dir: str                    # run() 传入的基准目录，全流程不变，如 ./output
    app_output_dir: str                     # 实际写入目录 = output_base_dir/应用名，由 BackendExpert 解析写入（专家池层面决定，不在 Commander 阶段）
    error_message: Optional[str]            # 最后一次错误信息
