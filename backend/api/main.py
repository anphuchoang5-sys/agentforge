"""
main.py — FastAPI 应用入口
B 核心产出物 · 对齐系统架构.html「② API 层」

启动方式：
    uvicorn backend.api.main:app --reload --port 8000
"""

from dotenv import load_dotenv
load_dotenv()  # 必须在所有其他 import 之前，确保 .env 中的环境变量已加载

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.observability import setup_tracing
from backend.api.routes import tasks, websocket, metrics
from backend.tools.console_encoding import ensure_utf8_console

# 进程真正的入口点，不依赖 routes 的 import 链间接触发（那样等于把这个
# 保证藏在"恰好谁先 import 谁"的偶然顺序里）——直接在这里显式调用一次，
# 覆盖后台线程池里跑的整条流水线的所有 print()（problem.md 第31条）。
ensure_utf8_console()

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
