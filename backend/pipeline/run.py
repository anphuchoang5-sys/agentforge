"""
run.py — B 的全流程入口
B 核心产出物

run(user_input) 是 B 对外暴露的唯一接口：
  输入：用户一句话需求
  输出：{"deliverable": "zip路径", "test_report": {...}, "app_path": "主文件路径"}
"""

import os
import zipfile
from backend.graph.project_state import ProjectState
from backend.graph.workflow import build_graph


def _zip_output(output_dir: str) -> str:
    """把生成的代码文件夹打成 zip"""
    zip_path = output_dir.rstrip("/") + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(output_dir):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, output_dir)
                zf.write(full_path, arcname)
    print(f"[run] 打包完成: {zip_path}")
    return zip_path


def run(user_input: str, output_dir: str = "./output") -> dict:
    """全流程入口：用户需求 → 代码生成 → 返回交付物

    Args:
        user_input: 用户的一句话需求，如「做一个待办事项桌面应用」
        output_dir: 代码落盘的根目录（基准目录）。
            实际子目录名由 Commander 拆解出的接口规范自动派生
            （如 create_todo/delete_todo → todo/），不需要调用方手动指定。

    Returns:
        {
            "deliverable": "./output/todo.zip",
            "app_path": "./output/todo/app.py",
            "test_report": {
                "backend_generated": True,
                "frontend_generated": True,
                "iterations": 1,
                "validation_passed": True,
            }
        }
    """
    print(f"\n{'='*50}")
    print(f"[run] 开始处理: {user_input}")
    print(f"{'='*50}\n")

    # 初始状态：大白板，只有用户输入有值，其余等各 Agent 跑完后填入
    initial_state: ProjectState = {
        # ── 用户输入（一开始就有）──────────────────────────────
        "user_input": user_input,           # 用户的原始需求，如"做一个待办事项应用"

        # ── A 填（Commander 拆解后写入）────────────────────────
        "task_decomposition": None,         # 拆解结果：接口规范 + 任务清单

        # ── BackendExpert 填────────────────────────────────────
        "backend_code": None,               # 生成的后端代码字符串（SQLite 数据层）
        "backend_path": None,               # 代码存到硬盘的路径，如 ./output/db.py

        # ── FrontendExpert 填───────────────────────────────────
        "frontend_code": None,              # 生成的前端代码字符串（Tkinter 界面）
        "frontend_path": None,              # 代码存到硬盘的路径，如 ./output/app.py

        # ── TestExpert 填───────────────────────────────────────
        "test_code": None,                  # 生成的 pytest 测试代码字符串
        "test_path": None,                  # 测试文件存到硬盘的路径
        "test_results": None,               # pytest 真实运行的输出，如 "3 passed, 0 failed"
        "test_passed": None,                # 测试是否全部通过，True 或 False

        # ── Validator（C）填────────────────────────────────────
        "validation_passed": None,          # C 验证是否通过，True 或 False
        "validation_logs": None,            # C 验证的详细日志列表
        "screenshot_path": None,            # C 截图存的路径（C 上线后才有值）

        # ── 流程控制（B 维护）──────────────────────────────────
        "iteration_count": 0,               # 当前重试轮数，超过 5 次强制终止
        "output_base_dir": output_dir,      # 基准目录，全流程不变
        "app_output_dir": output_dir,       # 初始等于基准目录，BackendExpert 解析出真实应用名后会覆盖
        "error_message": None,              # 出错时记录原因，方便排查
    }

    # 跑状态机
    # graph.invoke 内部会依次触发 decompose_node（调 A 的 decompose()）
    # 和 validator_node（调 C 的 validate()，见 backend/agents/validator_stub.py）。
    # C 上线前 validate() 走本地 Mock；C 上线后只需在 .env 加 VALIDATOR_URL，
    # 这里的调用逻辑不用改——对应最终分工表接口③（B 调 C：app_path → 测试报告）。
    graph = build_graph()
    final_state = graph.invoke(initial_state)

    # 打包交付物（用 BackendExpert 解析后的真实目录，不是最初的基准目录）
    final_output_dir = final_state["app_output_dir"]
    deliverable = _zip_output(final_output_dir)

    result = {
        "deliverable": deliverable,
        "app_path": final_state.get("frontend_path"),
        "test_report": {
            "backend_generated": bool(final_state.get("backend_code")),
            "frontend_generated": bool(final_state.get("frontend_code")),
            "iterations": final_state.get("iteration_count", 0),
            "validation_passed": final_state.get("validation_passed", False),
        },
    }

    print(f"\n[run] 完成！交付物: {deliverable}")
    return result
