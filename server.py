"""
server.py
Backend API 入口 (FastAPI)
重构版本 v4.2.0 - 生产环境就绪 (启用自动同步)
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

from api.dependencies import get_cache_wrapper

# 引入路由模块
from api.routes import admin, chat, files, system

# 引入核心容器
from core.container import container

# 引入中间件和后台任务
from middleware.error_handler import register_exception_handlers
from middleware.metrics import PrometheusMiddleware, metrics_endpoint
from services.sync_service import auto_sync_scheduler  # 确保导入了同步调度器

logger = logging.getLogger(__name__)


# --- ⏳ 生命周期管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 [System] Starting up...")

    # 1. Redis 连接测试
    try:
        container.redis_client()
    except Exception as e:
        logger.critical(f"❌ Redis Init Failed: {e}")
        raise e

    # 2. 启动健康检查 (Health Check)
    cache = get_cache_wrapper()
    health_task = asyncio.create_task(cache.start_health_check())

    # 3. 🟢 [已恢复] 启动 Notion 自动同步任务
    # 在生产环境中，这是保持数据新鲜的关键
    config = container.config()
    sync_task = asyncio.create_task(
        auto_sync_scheduler(
            db_id=config.DB_SPANISH_ID,
            notion_token=config.NOTION_TOKEN,
            # 注意：传入容器的"获取器"方法，而不是实例本身，防止闭包过早绑定
            get_vector_store_func=container.vector_store,
            get_config_func=container.config,
        )
    )
    logger.info("🚀 [System] Background Sync Task started.")

    yield

    logger.info("🛑 [System] Shutting down...")

    # 取消所有后台任务
    sync_task.cancel()
    health_task.cancel()
    try:
        await sync_task
        await health_task
    except asyncio.CancelledError:
        pass

    # 清理资源
    from infrastructure.cache.redis_client import RedisClient

    RedisClient.close()
    logger.info("🛑 [System] Cleanup complete.")


# --- 🚀 初始化 APP ---
settings = container.config()

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    version="4.2.0-Prod",
    debug=settings.DEBUG,
)

# === 🔥 一键注册所有异常处理器 ===
register_exception_handlers(app)

# === 注册路由 ===
app.add_route("/metrics", metrics_endpoint)  # 监控接口
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(admin.router)
app.include_router(system.router)

# === 限流器配置 ===
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# === 中间件 ===
app.add_middleware(SessionMiddleware, secret_key=settings.API_SECRET)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PrometheusMiddleware)  # 监控中间件

# === 静态文件 ===

if not os.path.exists(settings.AUDIO_DIR):
    os.makedirs(settings.AUDIO_DIR)
app.mount("/audio", StaticFiles(directory=settings.AUDIO_DIR), name="audio")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
