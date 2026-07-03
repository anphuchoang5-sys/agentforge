"""
observability.py — 可观测层：OpenTelemetry 埋点
B 核心产出物 · 对齐系统架构.html「⑧ 可观测层」

默认导出到控制台（不需要预先起 Jaeger 就能看追踪信息）；
配置 OTEL_EXPORTER_OTLP_ENDPOINT 后自动改用 OTLP 导出（对接 Jaeger/Docker），
调用方不需要改代码。
"""

import os
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

_initialized = False


def setup_tracing() -> None:
    """初始化一次 TracerProvider，重复调用是安全的（只生效一次）"""
    global _initialized
    if _initialized:
        return

    resource = Resource.create({"service.name": "agentforge-backend"})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _initialized = True


def get_tracer():
    setup_tracing()
    return trace.get_tracer("agentforge.pipeline")


@contextmanager
def node_span(node_name: str, **attributes):
    """给单个 LangGraph 节点执行包一个 span，供 Agent 调用链追踪用

    注意：stream_mode="updates" 只在节点跑完时才吐出结果，这里的 span
    只能包住"收到结果后处理"这一小段，不是节点真实执行耗时——如果要精确
    到节点真实起止时间，需要改用 LangChain callbacks（on_chain_start/end），
    属于后续可以加深的埋点粒度，先满足"能看到调用链顺序"这个最低要求。
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(
        node_name,
        attributes={"agent": node_name, **attributes},
    ) as span:
        yield span
