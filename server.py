"""
Biobrain Server Entry Point
版本：v4.7 (Routes Directory Fix)
描述：FastAPI 主应用入口。
修复：修正导入路径以指向 api/routes/ 目录。
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import SETTINGS
from core.container import container
from middleware.bandwidth_limiter import BandwidthLimiterMiddleware
from middleware.error_handler import register_exception_handlers

# ✅ 新增：导入监控中间件和处理函数
from middleware.metrics import PrometheusMiddleware, metrics_endpoint
from utils.logger import setup_logging

# 1. 路由模块导入 (修正路径：api.routes.*)
# -------------------------------------------------------------------------
try:
    from api.routes.admin import router as admin_router  # api/routes/admin.py
    from api.routes.chat import router as chat_router  # api/routes/chat.py
    from api.routes.files import router as files_router  # api/routes/files.py
    from api.routes.system import router as system_router  # api/routes/system.py

except ImportError as e:
    # 打印详细错误以帮助调试
    import sys

    print(f"❌ 路由导入失败: {e}")
    print(f"   当前 sys.path: {sys.path[:2]}")
    raise e
# -------------------------------------------------------------------------

# 初始化日志
setup_logging()
logger = logging.getLogger("biobrain.server")


async def auto_cleanup_scheduler(interval_seconds: int = 300):
    """
    自动清理闲置模型的调度器

    定期检查并卸载闲置的稀疏模型和重排序模型以释放内存
    """
    logger.info(f"🔄 Starting auto cleanup scheduler (interval: {interval_seconds}s)")
    while True:
        try:
            # 获取容器实例
            from core.container import container

            vector_store = container.vector_store()
            unloaded_count = 0

            # 卸载稀疏模型
            if hasattr(vector_store, "auto_unload_idle_models"):
                if vector_store.auto_unload_idle_models():
                    unloaded_count += 1

            # 卸载重排序模型
            try:
                hybrid_engine = container.hybrid_search_engine()
                if hasattr(hybrid_engine, "auto_unload_idle_models"):
                    if hybrid_engine.auto_unload_idle_models():
                        unloaded_count += 1
            except Exception as e:
                logger.warning(f"Failed to unload reranker model: {e}")

            if unloaded_count > 0:
                logger.info(f"🗑️ Auto cleanup unloaded {unloaded_count} idle model(s)")

        except Exception as e:
            logger.error(f"❌ Auto cleanup scheduler error: {e}")

        # 等待下一个周期
        await asyncio.sleep(interval_seconds)


# 2. 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Biobrain Server starting up...")

    # 连接预热
    try:
        _ = container.vector_store().client
        logger.info("✅ Vector Store connection verified.")
    except Exception as e:
        logger.error(f"❌ Vector Store connection failed: {e}")

    # 启动自动清理调度器
    cleanup_task = asyncio.create_task(auto_cleanup_scheduler())
    logger.info("🔄 Auto cleanup scheduler started (interval: 300s)")

    yield

    # 关闭清理
    logger.info("🛑 Biobrain Server shutting down...")

    # 停止自动清理调度器
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


# 3. App 初始化
app = FastAPI(
    title="Biobrain API",
    version="4.3.0",
    description="AI Second Brain with Notion & Qdrant Integration",
    lifespan=lifespan,
)

# 4. 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ✅ 新增：注册 Prometheus 监控中间件
app.add_middleware(PrometheusMiddleware)
app.add_middleware(BandwidthLimiterMiddleware, max_bandwidth_mb=50)

# 5. 异常处理 - 注册所有标准异常处理器
register_exception_handlers(app)

# 6. 注册路由
app.include_router(chat_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")
app.mount(
    "/generated_audio",
    StaticFiles(directory=SETTINGS.AUDIO_DIR),
    name="generated_audio",
)


# ✅ 新增：注册监控指标接口
@app.get("/metrics", tags=["System"])
def metrics(request: Request):
    return metrics_endpoint(request)


# 根路径健康检查
@app.get("/health", tags=["System"])
async def root_health_check():
    return {"status": "healthy", "service": "biobrain-server"}


# 内存监控端点
@app.get("/api/memory", tags=["System"])
async def get_memory_usage():
    """
    获取系统内存使用情况和模型加载状态
    """
    try:
        import psutil

        # 获取进程内存信息
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # 转换为MB

        # 获取系统内存信息
        system_memory = psutil.virtual_memory()

        # 获取模型状态
        from core.container import container

        vector_store = container.vector_store()

        sparse_model_stats = {}
        reranker_stats = {}

        try:
            # 获取稀疏模型统计信息
            if hasattr(vector_store, "get_sparse_model_stats"):
                sparse_model_stats = vector_store.get_sparse_model_stats()
        except Exception as e:
            sparse_model_stats = {"error": str(e)}

        # 尝试获取重排序模型统计信息（如果可用）
        try:
            hybrid_engine = container.hybrid_search_engine()
            if hasattr(hybrid_engine, "get_reranker_stats"):
                reranker_stats = hybrid_engine.get_reranker_stats()
        except Exception as e:
            reranker_stats = {"error": str(e)}

        # 检查配置
        config_info = {}
        try:
            if SETTINGS:
                config_info = {
                    "ENABLE_SPARSE_MODEL": getattr(
                        SETTINGS, "ENABLE_SPARSE_MODEL", True
                    ),
                    "ENABLE_RERANKER": getattr(SETTINGS, "ENABLE_RERANKER", True),
                    "MAX_MEMORY_MB": getattr(SETTINGS, "MAX_MEMORY_MB", 2048),
                    "SPARSE_MODEL_NAME": getattr(
                        SETTINGS, "SPARSE_MODEL_NAME", "prithivida/Splade_PP_en_v1"
                    ),
                    "RERANKER_MODEL_NAME": getattr(
                        SETTINGS, "RERANKER_MODEL_NAME", "BAAI/bge-reranker-large"
                    ),
                }
        except Exception:
            pass

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
            "warnings": [
                f"Process using {round(memory_mb, 2)}MB of memory",
                f"System memory {round(system_memory.percent, 2)}% used",
            ]
            if memory_mb > 1500 or system_memory.percent > 80
            else [],
        }

    except ImportError:
        return {
            "error": "psutil not available for memory monitoring",
            "suggestion": "Install psutil: pip install psutil",
        }
    except Exception as e:
        return {"error": f"Memory monitoring failed: {str(e)}"}


# 内存清理端点
@app.post("/api/memory/cleanup", tags=["System"])
async def cleanup_idle_models():
    """
    清理闲置模型以释放内存
    """
    import time

    try:
        from core.container import container

        vector_store = container.vector_store()
        unloaded_count = 0

        # 卸载稀疏模型
        if hasattr(vector_store, "auto_unload_idle_models"):
            if vector_store.auto_unload_idle_models():
                unloaded_count += 1

        # 尝试卸载重排序模型（如果可用）
        try:
            hybrid_engine = container.hybrid_search_engine()
            if hasattr(hybrid_engine, "auto_unload_idle_models"):
                if hybrid_engine.auto_unload_idle_models():
                    unloaded_count += 1
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Failed to unload reranker model: {e}")

        return {
            "success": True,
            "message": f"Cleaned up {unloaded_count} idle model(s)",
            "unloaded_count": unloaded_count,
            "timestamp": time.time(),
        }

    except Exception as e:
        return {"success": False, "error": str(e), "timestamp": time.time()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        # 🔥 关键修复：排除不需要监控的目录和文件
        # 防止数据库写入或前端构建触发后端重启
        reload_excludes=[
            "web/*",  # 忽略前端目录
            "storage/*",  # 忽略 Qdrant 存储 (如果有)
            "*.db",  # 忽略 SQLite 数据库
            "*.sqlite",
            "*.pyc",
            ".cache/*",  # 忽略缓存
            "__pycache__/*",
            ".git/*",
        ],
    )
