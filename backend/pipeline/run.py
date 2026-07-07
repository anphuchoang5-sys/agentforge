"""
run.py — B 的全流程入口
B 核心产出物

run(user_input) 是 B 对外暴露的唯一接口：
  输入：用户一句话需求
  输出：{"deliverable": "zip路径", "test_report": {...}, "app_path": "主文件路径",
        "passed": ..., "logs": [...], "screenshot": "...", "failed_tests": [...], "iteration": ...}
        （后四项 + passed/iteration 是 C 的 Validator 原始报告字段，供前端直接读取）
"""

import os
import zipfile
from typing import Callable, Optional
from backend.graph.project_state import ProjectState
from backend.graph.workflow import build_graph
from backend.api.observability import get_tracer, node_span
from backend.tools.console_encoding import ensure_utf8_console

# run.py 是整条流水线唯一入口，这里统一确保 UTF-8 控制台一次，覆盖后面
# 所有节点（Commander/三专家/Validator）的 print()——不用每冒出一个新的
# emoji print 就在那个文件里单独补一次（problem.md 第31条同一类问题，
# 这次冒烟测试在 test_expert.py 新加的 collect-only 失败分支里真实复现过）。
ensure_utf8_console()


def _zip_output(output_dir: str) -> str:
    """把生成的代码文件夹打成 zip"""
    if not os.path.isdir(output_dir):
        raise RuntimeError(f"输出目录不存在，拒绝打包: {output_dir}")
    files_to_pack = [
        os.path.join(root, file)
        for root, _, files in os.walk(output_dir)
        for file in files
    ]
    if not files_to_pack:
        raise RuntimeError(f"输出目录为空，拒绝打包空交付物: {output_dir}")

    zip_path = output_dir.rstrip("/") + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for full_path in files_to_pack:
            arcname = os.path.relpath(full_path, output_dir)
            zf.write(full_path, arcname)
    print(f"[run] 打包完成: {zip_path}")
    return zip_path


def run(
    user_input: str,
    output_dir: str = "./output",
    on_event: Optional[Callable[[str, dict], None]] = None,
) -> dict:
    """全流程入口：用户需求 → 代码生成 → 返回交付物

    Args:
        user_input: 用户的一句话需求，如「做一个待办事项桌面应用」
        output_dir: 代码落盘的根目录（基准目录）。
            实际子目录名由 Commander 拆解出的接口规范自动派生
            （如 create_todo/delete_todo → todo/），不需要调用方手动指定。
        on_event: 可选回调，每个 LangGraph 节点跑完立刻触发一次，
            签名 (node_name: str, node_output: dict) -> None。
            不传就是原来的行为（一次性跑完再返回），供 API 层做实时推送用，
            不传不影响任何现有调用方（比如直接 import run() 的测试脚本）。

    Returns:
        {
            "deliverable": "./output/todo.zip",
            "app_path": "./output/todo/app.py",
            "test_report": {
                "backend_generated": True,
                "frontend_generated": True,
            },
            # 下面这几项是 C 的 Validator 原始报告（TestReport）字段，供前端
            # done 事件里的截图/失败用例/通过角标直接读取（对齐 CLAUDE.md 里
            # C 的对外接口）。是否验证通过/第几轮只在这里存一份——之前
            # test_report 里也重复放过 validation_passed/iterations，
            # 全仓库没人读，属于纯冗余，已经收掉。
            "passed": True,
            "logs": ["[compile] ok", "[ruff] no issues", "..."],
            "screenshot": "base64 PNG 或空串",
            "failed_tests": [{"name": "...", "reason": "...", "severity": "error"}],
            "iteration": 1,
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
        "pytest_report_path": None,         # pytest --json-report 生成的 JSON 报告路径

        # ── Validator（C）填────────────────────────────────────
        "validation_passed": None,          # C 验证是否通过，True 或 False
        "validation_logs": None,            # C 验证的详细日志列表
        "screenshot_path": None,            # C 截图存的路径（C 上线后才有值）
        "failed_tests": None,               # C 的 TestReport.failed_tests，逐条失败项

        # ── 流程控制（B 维护）──────────────────────────────────
        "iteration_count": 0,               # 当前重试轮数，超过 5 次强制终止
        "output_base_dir": output_dir,      # 基准目录，全流程不变
        "app_output_dir": output_dir,       # 初始等于基准目录，BackendExpert 解析出真实应用名后会覆盖
        "error_message": None,              # 出错时记录原因，方便排查
    }

    # 跑状态机（节点内部依次调用 A 的 decompose() 和 C 的 validate()，
    # 见 workflow.py 的 decompose_node / validator_node）
    graph = build_graph()
    tracer = get_tracer()

    with tracer.start_as_current_span("run", attributes={"user_input": user_input}):
        # 图执行本身不包 try/except——LangGraph 节点内部（decompose_node/
        # validator_node）按项目原则该抛的异常会原样抛出来，这里只是把裸的
        # 内部异常（可能是 Pydantic 校验错误、LangGraph 内部报错等，单看
        # 类型/message 不知道是 run() 的哪一步炸的）包装成一条说得清楚
        # "是需求处理流程失败"的 RuntimeError，不是把失败吞掉或伪装成功
        # （problem.md 第29条）
        try:
            if on_event is None:
                final_state = graph.invoke(initial_state)
            else:
                # stream_mode="updates" 每个节点跑完就吐一次 {节点名: 该节点返回的增量dict}，
                # 不用等整张图跑完，可以实时往外推。手动把每次增量合并成完整 final_state
                # （LangGraph 内部 invoke() 也是做的同样的合并，这里只是自己再做一遍）。
                final_state = dict(initial_state)
                for chunk in graph.stream(initial_state, stream_mode="updates"):
                    for node_name, node_output in chunk.items():
                        final_state.update(node_output)
                        with node_span(node_name):
                            on_event(node_name, node_output)
        except Exception as e:
            raise RuntimeError(
                f"代码生成流程执行失败（需求：{user_input!r}）："
                f"{type(e).__name__}: {e}"
            ) from e

        # 打包交付物之前先确认真的生成出东西了——没有任何代码产出的话，
        # _zip_output() 对着一个空/不存在的目录跑不会报错，只会静默产出一个
        # "格式合法但内容为空"的 zip 冒充交付物，这正是 CLAUDE.md 明确禁止的
        # "静默兜底成假成功"（problem.md 第29条），必须在这里主动拦下来
        final_output_dir = final_state["app_output_dir"]
        required_outputs = {
            "BackendExpert.backend_code": final_state.get("backend_code"),
            "BackendExpert.backend_path": final_state.get("backend_path"),
            "FrontendExpert.frontend_code": final_state.get("frontend_code"),
            "FrontendExpert.frontend_path": final_state.get("frontend_path"),
            "TestExpert.test_code": final_state.get("test_code"),
            "TestExpert.test_path": final_state.get("test_path"),
            "TestExpert.pytest_report_path": final_state.get("pytest_report_path"),
        }
        missing = [name for name, value in required_outputs.items() if not value]
        if missing:
            raise RuntimeError(
                f"代码生成流程缺少真实产出（需求：{user_input!r}，输出目录：{final_output_dir}）："
                + ", ".join(missing)
            )

        missing_files = [
            name for name in (
                "backend_path", "frontend_path", "test_path", "pytest_report_path"
            )
            if not os.path.exists(final_state[name])
        ]
        if missing_files:
            raise RuntimeError(
                "代码生成流程记录了路径但文件不存在: " + ", ".join(missing_files)
            )

        deliverable = _zip_output(final_output_dir)

        result = {
            "deliverable": deliverable,
            "app_path": final_state.get("frontend_path"),
            # test_report 只保留没有别处能拿到的信息（是否生成出代码）；
            # 验证是否通过/第几轮，全仓库 grep 确认没有任何后端或前端代码
            # 读取过 test_report.validation_passed/test_report.iterations，
            # 一直是写了没人读的重复字段——单一数据源统一放到下面的
            # passed/iteration（跟 C 的 Validator 原始报告字段放在一起）。
            "test_report": {
                "backend_generated": bool(final_state.get("backend_code")),
                "frontend_generated": bool(final_state.get("frontend_code")),
            },
            # C 的 Validator 原始报告字段（对齐 CLAUDE.md 里 C 的对外接口
            # {"passed","logs","screenshot","failed_tests"}）——之前这里只有
            # 上面的 test_report 摘要，前端 agentClient.ts 的 isValidatorPayload/
            # applyValidatorResult 一直在等的是这几个顶层字段，done 事件里根本
            # 没传过，导致截图/失败用例/通过角标接真实后端时永远不会被填充。
            "passed": final_state.get("validation_passed", False),
            "logs": final_state.get("validation_logs") or [],
            "screenshot": final_state.get("screenshot_path") or "",
            "failed_tests": final_state.get("failed_tests") or [],
            "iteration": final_state.get("iteration_count", 0),
        }

    print(f"\n[run] 完成！交付物: {deliverable}")
    return result
