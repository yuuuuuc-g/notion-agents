"""
Biobrain Server Entry Point
版本：v4.7 (Routes Directory Fix)
描述：FastAPI 主应用入口。
修复：修正导入路径以指向 api/routes/ 目录。
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config.settings import SETTINGS
from core.container import container
from middleware.bandwidth_limiter import BandwidthLimiterMiddleware
from middleware.error_handler import global_exception_handler

# ✅ 新增：导入监控中间件和处理函数
from middleware.metrics import PrometheusMiddleware, metrics_endpoint
from services.sync_service import auto_sync_scheduler
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

    # 后台同步任务
    sync_task = asyncio.create_task(auto_sync_scheduler(SETTINGS.DB_SPANISH_ID))
    yield

    # 关闭清理
    logger.info("🛑 Biobrain Server shutting down...")
    sync_task.cancel()
    try:
        await sync_task
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

# 5. 异常处理
app.add_exception_handler(Exception, global_exception_handler)

# 6. 注册路由
app.include_router(chat_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.include_router(admin_router, prefix="/api/admin")


# ✅ 新增：注册监控指标接口
@app.get("/metrics", tags=["System"])
def metrics(request: Request):
    return metrics_endpoint(request)


# 根路径健康检查
@app.get("/health", tags=["System"])
async def root_health_check():
    return {"status": "healthy", "service": "biobrain-server"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
