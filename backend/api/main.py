"""
main.py — FastAPI 应用入口
B 核心产出物 · 对齐系统架构.html「② API 层」

启动方式：
    uvicorn backend.api.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.observability import setup_tracing
from backend.api.routes import tasks, websocket, metrics

setup_tracing()

app = FastAPI(title="AgentForge API")

# 本地开发：Vite 默认跑在 5173，前后端分离，需要放开 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks.router)
app.include_router(websocket.router)
app.include_router(metrics.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
