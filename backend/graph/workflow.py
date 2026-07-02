"""
workflow.py — LangGraph 状态机（完整版）
B 核心产出物

完整流水线：
Commander → BackendExpert ‖ FrontendExpert ‖ TestExpert → Validator → 重试/完成
"""

from langgraph.graph import StateGraph, END
from backend.graph.project_state import ProjectState
from backend.agents.experts.backend_expert import backend_expert_node
from backend.agents.experts.frontend_expert import frontend_expert_node
from backend.agents.experts.test_expert import test_expert_node


def decompose_node(state: ProjectState) -> dict:
    """调用 A 的 decompose，把结果写进白板

    只做需求拆解，不掺杂输出目录怎么定——目录名的解析在专家池层面
    （output_naming.resolve_output_dir，由 BackendExpert 落地），
    不是 Commander 该管的事。
    """
    from backend.agents.commander import decompose
    print(f"[Commander] 拆解需求: {state['user_input']}")
    result = decompose(state["user_input"])
    return {"task_decomposition": result}


def validator_node(state: ProjectState) -> dict:
    """把 C 的验证接口包装成 LangGraph 节点

    validate() 是同学 C 真正要实现的函数（对应最终分工表接口③：
    app_path → {passed, logs, screenshot, failed_tests}），现在
    backend/agents/validator_stub.py 里放的是占位 Mock 实现。
    这里只负责调用 + 把返回结果的字段映射进 ProjectState 白板，
    C 上线后只需在 validator_stub.py 内部切换成真实调用（见其文件内注释），
    本函数和整张图都不用改。
    """
    from backend.agents.validator_stub import validate
    report = validate(
        app_path=state.get("frontend_path", ""),
        test_results=state.get("test_results", ""),
    )
    return {
        "validation_passed": report["passed"],
        "validation_logs": report["logs"],
        "screenshot_path": report.get("screenshot"),
    }


def count_iteration(state: ProjectState) -> dict:
    """每次进入重试循环，计数 +1"""
    return {"iteration_count": state.get("iteration_count", 0) + 1}


def should_retry(state: ProjectState) -> str:
    """条件边：通过 → done，失败且未超限 → retry"""
    if state.get("validation_passed"):
        return "done"
    if state.get("iteration_count", 0) >= 5:
        print("[Validator] 已达最大重试次数(5)，强制终止")
        return "done"
    print(f"[Validator] 第{state.get('iteration_count',0)}轮未通过，重试...")
    return "retry"


def build_graph() -> StateGraph:
    graph = StateGraph(ProjectState)

    # 注册节点
    graph.add_node("decompose", decompose_node)
    graph.add_node("backend_expert", backend_expert_node)
    graph.add_node("frontend_expert", frontend_expert_node)
    graph.add_node("test_expert", test_expert_node)
    graph.add_node("validator", validator_node)
    graph.add_node("count", count_iteration)

    # 起点
    graph.set_entry_point("decompose")

    # decompose 完成 → Backend 和 Frontend 并行
    graph.add_edge("decompose", "backend_expert")
    graph.add_edge("decompose", "frontend_expert")

    # TestExpert 依赖 BackendExpert（需要读 backend_code）
    graph.add_edge("backend_expert", "test_expert")

    # 只留一条边进入 validator：test_expert → validator。
    #
    # 之前这里是两条独立边（test_expert → validator 和 frontend_expert → validator），
    # 结果 validator/count 每轮被触发 2 次（frontend_expert 先完成单独触发一次，
    # test_expert 后完成又触发一次），iteration_count 消耗速度是设计值的两倍。
    # 改成 add_edge([a, b], target) 形式的"汇合边"更看似正确，但已经验证会把重试
    # 循环彻底卡死——retry 只会跳回 backend_expert，frontend_expert 不会重新触发，
    # 汇合边要求"这两个都要在本轮触发"的条件从第二轮起永远凑不齐，validator 之后
    # 再也不会执行。
    #
    # 所以正确做法是只留 test_expert → validator 这一条边。安全性依赖 LangGraph
    # 的 Pregel/BSP 执行模型：backend_expert 和 frontend_expert 同属一个 superstep，
    # 同一个 superstep 里的所有节点必须全部完成，才会进入下一个 superstep
    # （test_expert 所在的那一步）——哪怕 test_expert 在图里只连着 backend_expert
    # 这一条边，它也不会在 frontend_expert 还没完成时抢跑，validator 读到的
    # state["frontend_path"] 必然已经写好。
    #
    # 但这个同步行为目前是 LangGraph 自己承认的未修复 bug，不是官方文档承诺的
    # 稳定契约（见 https://github.com/langchain-ai/langgraph/issues/6320，
    # 2025-10-21 提交，标记为 confirmed bug，截至现在未修复）。如果未来升级
    # LangGraph 后这个行为被"修复"，test_expert 理论上有可能在 frontend_expert
    # 完成前抢跑——不过 validator_node 用的是 state.get("frontend_path", "")，
    # 抢跑时最坏情况是这一轮验证失败触发重试，不会崩溃或产生脏数据，重试轮次里
    # frontend_expert 已经跑完，值就会补上。
    graph.add_edge("test_expert", "validator")

    # validator → 计数 → 条件边
    graph.add_edge("validator", "count")
    graph.add_conditional_edges(
        "count",
        should_retry,
        {
            "done": END,
            "retry": "backend_expert",  # 重试从专家节点重新开始
        },
    )

    return graph.compile()
