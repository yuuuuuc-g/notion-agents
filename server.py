"""
Biobrain Server Entry Point
版本：v4.9 (Code Review Fixed & Auto-Sync Enabled)
修复：
  - 删除 reload=False 时无效的 reload_excludes（死代码）
  - CORS: allow_credentials 改为 False（单机项目不需要）
  - lifespan 预创建 AUDIO_DIR，防止 StaticFiles 启动崩溃
  - 删除端点函数内多余的 `from core.container import container`
  - 恢复后台自动同步调度器 (auto_sync_scheduler)
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address

from config.settings import SETTINGS
from core.container import container
from middleware.bandwidth_limiter import BandwidthLimiterMiddleware
from middleware.error_handler import register_exception_handlers
from middleware.metrics import PrometheusMiddleware, metrics_endpoint

# 🔥 引入后台自动同步调度器
from services.sync_service import auto_sync_scheduler
from utils.logger import setup_logging

# 🔥 全局 SlowAPI Limiter 实例（供路由使用）
limiter = Limiter(key_func=get_remote_address)

# 路由导入
try:
    from api.routes.admin import router as admin_router
    from api.routes.chat import router as chat_router
    from api.routes.files import router as files_router
    from api.routes.graph import router as graph_router
    from api.routes.notion import router as notion_router
    from api.routes.system import router as system_router
except ImportError as e:
    import sys

    print(f"❌ 路由导入失败: {e}")
    print(f"   当前 sys.path: {sys.path[:2]}")
    raise e

setup_logging()
logger = logging.getLogger("biobrain.server")


# ==========================================
# 自动清理调度器
# ==========================================
async def auto_cleanup_scheduler(interval_seconds: int = 120):
    """定期检查并卸载闲置模型以释放内存"""
    logger.info(f"🔄 Starting auto cleanup scheduler (interval: {interval_seconds}s)")

    while True:
        try:
            vector_store = container.vector_store()
            unloaded_count = 0

            if hasattr(vector_store, "auto_unload_idle_models"):
                if await asyncio.to_thread(vector_store.auto_unload_idle_models):
                    unloaded_count += 1

            try:
                hybrid_engine = container.hybrid_search_engine()
                if hasattr(hybrid_engine, "auto_unload_idle_models"):
                    if await asyncio.to_thread(hybrid_engine.auto_unload_idle_models):
                        unloaded_count += 1
            except Exception as e:
                logger.warning(f"Failed to unload reranker model: {e}")

            if unloaded_count > 0:
                logger.info(f"🗑️ Auto cleanup unloaded {unloaded_count} idle model(s)")

        except Exception as e:
            logger.error(f"❌ Auto cleanup scheduler error: {e}")

        await asyncio.sleep(interval_seconds)


# ==========================================
# 生命周期管理
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Biobrain Server starting up...")

    # 🔥 预创建音频目录，防止 StaticFiles 崩溃
    os.makedirs(SETTINGS.AUDIO_DIR, exist_ok=True)

    # 连接预热
    try:
        _ = container.vector_store().client
        logger.info("✅ Vector Store connection verified.")
    except Exception as e:
        logger.error(f"❌ Vector Store connection failed: {e}")

    # 1. 启动自动清理调度器
    cleanup_task = asyncio.create_task(auto_cleanup_scheduler())
    logger.info("🔄 Auto cleanup scheduler started (interval: 300s)")

    # 2. Notion 自动同步调度器
    notion_db_id = "2c535e6b0ea580ce8170d8c0bebff29a"
    logger.info(f"🚀 [Startup] Creating auto-sync task for DB: {notion_db_id}...")
    sync_task = asyncio.create_task(auto_sync_scheduler(db_id=notion_db_id))
    logger.info("✅ [Startup] Notion auto-sync scheduler task created and running.")

    yield

    # ── Shutdown ──
    logger.info("🛑 Biobrain Server shutting down...")

    # 优雅地取消所有后台任务
    logger.info("🛑 [Shutdown] Cancelling cleanup_task...")
    cleanup_task.cancel()
    logger.info("🛑 [Shutdown] Cancelling sync_task...")
    sync_task.cancel()

    try:
        await asyncio.gather(cleanup_task, sync_task, return_exceptions=True)
        logger.info("✅ [Shutdown] All background tasks cancelled successfully.")
    except asyncio.CancelledError:
        logger.info("✅ [Shutdown] Tasks cancelled (CancelledError caught).")
    logger.info("✅ All background tasks gracefully shut down.")


# ==========================================
# App 初始化
# ==========================================
app = FastAPI(
    title="Biobrain API",
    version="4.9.0",
    description="AI Second Brain with Notion & Qdrant Integration",
    lifespan=lifespan,
)

# 🔥 将 Limiter 挂载到 app.state（供路由使用）
app.state.limiter = limiter

# 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # 本地开发
        "https://gaoyucan.com",  # 生产环境主域名
        "https://www.gaoyucan.com",  # 备用域名
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(BandwidthLimiterMiddleware, max_bandwidth_mb=50)

# 异常处理
register_exception_handlers(app)

# 路由注册
app.include_router(chat_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(notion_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.include_router(graph_router, prefix="/api")

# 静态文件（音频）
os.makedirs(SETTINGS.AUDIO_DIR, exist_ok=True)  # 🔥 关键修复：在挂载前强制创建目录！
app.mount(
    "/generated_audio",
    StaticFiles(directory=SETTINGS.AUDIO_DIR),
    name="generated_audio",
)


# ==========================================
# 监控端点
# ==========================================
@app.get("/metrics", tags=["System"])
def metrics(request: Request):
    return metrics_endpoint(request)


@app.get("/health", tags=["System"])
async def root_health_check():
    return {"status": "healthy", "service": "biobrain-server"}


# ==========================================
# 内存监控
# ==========================================
@app.get("/api/memory", tags=["System"])
async def get_memory_usage():
    """获取系统内存使用情况和模型加载状态"""
    try:
        import psutil
    except ImportError:
        return {
            "error": "psutil not available",
            "suggestion": "pip install psutil",
        }

    try:
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024 * 1024)
        system_memory = psutil.virtual_memory()

        # 模型状态
        vector_store = container.vector_store()

        sparse_model_stats = {}
        reranker_stats = {}

        if hasattr(vector_store, "get_sparse_model_stats"):
            try:
                sparse_model_stats = vector_store.get_sparse_model_stats()
            except Exception as e:
                sparse_model_stats = {"error": str(e)}

        try:
            hybrid_engine = container.hybrid_search_engine()
            if hasattr(hybrid_engine, "get_reranker_stats"):
                reranker_stats = hybrid_engine.get_reranker_stats()
        except Exception as e:
            reranker_stats = {"error": str(e)}

        # 配置信息
        config_info = {
            "ENABLE_SPARSE_MODEL": getattr(SETTINGS, "ENABLE_SPARSE_MODEL", True),
            "ENABLE_RERANKER": getattr(SETTINGS, "ENABLE_RERANKER", True),
            "MAX_MEMORY_MB": getattr(SETTINGS, "MAX_MEMORY_MB", 1500),
            "SPARSE_MODEL_NAME": getattr(SETTINGS, "SPARSE_MODEL_NAME", "unknown"),
            "RERANKER_MODEL_NAME": getattr(SETTINGS, "RERANKER_MODEL_NAME", "unknown"),
        }

        warnings = []
        if memory_mb > 1500:
            warnings.append(f"Process using {round(memory_mb, 2)}MB of memory")
        if system_memory.percent > 80:
            warnings.append(f"System memory {round(system_memory.percent, 2)}% used")

        return {
            "process_memory_mb": round(memory_mb, 2),
            "system_memory": {
                "total_mb": round(system_memory.total / (1024 * 1024), 2),
                "available_mb": round(system_memory.available / (1024 * 1024), 2),
                "percent_used": round(system_memory.percent, 2),
            },
            "model_status": {
                "sparse_model": sparse_model_stats,
                "reranker_model": reranker_stats,
                "config": config_info,
            },
            "warnings": warnings,
        }

    except Exception as e:
        return {"error": f"Memory monitoring failed: {str(e)}"}


# ==========================================
# 内存清理
# ==========================================
@app.post("/api/memory/cleanup", tags=["System"])
async def cleanup_idle_models():
    """手动触发卸载闲置模型"""
    try:
        vector_store = container.vector_store()
        unloaded_count = 0

        if hasattr(vector_store, "auto_unload_idle_models"):
            if vector_store.auto_unload_idle_models():
                unloaded_count += 1

        try:
            hybrid_engine = container.hybrid_search_engine()
            if hasattr(hybrid_engine, "auto_unload_idle_models"):
                if hybrid_engine.auto_unload_idle_models():
                    unloaded_count += 1
        except Exception as e:
            logger.warning(f"Failed to unload reranker model: {e}")

        return {
            "success": True,
            "message": f"Cleaned up {unloaded_count} idle model(s)",
            "unloaded_count": unloaded_count,
            "timestamp": time.time(),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "timestamp": time.time()}


# ==========================================
# 入口（生产用 Dockerfile CMD，不需要这个）
# ==========================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
