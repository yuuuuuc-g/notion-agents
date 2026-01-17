"""
server.py
Backend API 入口 (FastAPI)
重构版本 - 降低耦合度，提取业务逻辑到服务层
"""
import asyncio
import os
import uuid
from functools import lru_cache
from typing import List, Optional

import redis
import uvicorn
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

# Agent 核心
from agent.agent_graph import graph
from config.settings import SETTINGS

# 🔥 引入业务服务层
from middleware.auth import generate_csrf_token, verify_token
from services.archive_service import archive_session
from services.file_parser import (
    extract_text_from_file,
    validate_file_type,
)
from services.sync_service import auto_sync_scheduler, sync_notion_database

# 🔧 引入日志模块
from utils.logger import get_logger

logger = get_logger(__name__)


# --- ⚙️ 配置注入工厂 ---
@lru_cache()
def get_config():
    """
    统一获取配置的工厂函数。
    使用 lru_cache 确保单例，方便后续测试 Mock。
    """
    return SETTINGS


# --- 🤖 模型注入工厂 ---
def get_model(model_name: str):
    """
    模型工厂：根据前端传来的 model_name，动态生成模型实例。
    """
    config = get_config()

    # 这里默认使用 SiliconFlow 适配 DeepSeek，你可以根据需要扩展逻辑
    return ChatOpenAI(
        model=model_name,
        openai_api_key=config.SILICON_KEY,
        openai_api_base="https://api.siliconflow.cn/v1",
        streaming=True,
    )


# --- 🏛️ 基础设施注入工厂 ---
from notion.notion_ops import NotionService  # noqa: E402
from vector.vector_store import LevelChunkVectorStore  # noqa: E402


@lru_cache()
def get_vector_store():
    """
    向量库工厂：确保全局只初始化一个向量库实例。
    """
    return LevelChunkVectorStore()


@lru_cache()
def get_notion_service(config=Depends(get_config)):
    """Notion 服务工厂"""
    return NotionService(
        token=config.NOTION_TOKEN,
        default_db_id=config.DB_TECH_ID or config.DB_SPANISH_ID,
    )


# --- 初始化 APP ---
app = FastAPI(
    title="Exocortex API",
    description="Backend service for Notion-Prism-React Agent",
    version="2.4.0",
)

# --- 🔒 配置限流器 ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 🔒 配置 Session ---
current_config = get_config()
# API_SECRET 已在配置加载时强制验证，这里可以直接使用
app.add_middleware(SessionMiddleware, secret_key=current_config.API_SECRET)

# --- 1. 配置 CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- 2. 初始化 Redis ---
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True,
)

try:
    redis_client.ping()
    logger.info("✅ Redis connection successful!")
except redis.ConnectionError:
    logger.warning("⚠️ Warning: Redis not connected. Cache will fail.")

# --- 3. 静态文件挂载 ---
if not os.path.exists(current_config.AUDIO_DIR):
    os.makedirs(current_config.AUDIO_DIR)
app.mount("/audio", StaticFiles(directory=current_config.AUDIO_DIR), name="audio")


# --- 5. 数据模型 ---
class ChatRequest(BaseModel):
    query: str
    thread_id: str = "default_user"
    file_id: Optional[str] = None
    model_name: Optional[str] = "deepseek/deepseek-chat"


class ChatResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None
    notion_url: Optional[str] = None
    thread_id: str


class ArchiveRequest(BaseModel):
    file_id: str
    summary: str = "User saved content"
    thread_id: str = "default"


# --- 6. 常量配置 ---
MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_TOTAL_SIZE = 100 * 1024 * 1024
MAX_FILES_COUNT = 10


# ============================
# 🚀 核心接口 (Endpoints)
# ============================


@app.post("/upload")
@limiter.limit("10/minute")
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    """文件上传接口"""
    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files. Maximum {MAX_FILES_COUNT} files allowed.",
        )

    combined_text = ""
    total_size = 0

    for file in files:
        # 读取文件内容
        content = await file.read()
        filename = file.filename.lower()
        file_size = len(content)

        # 🔒 检查单个文件大小
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' is too large. "
                f"Maximum size is {MAX_FILE_SIZE / (1024 * 1024):.1f} MB, "
                f"but got {file_size / (1024 * 1024):.2f} MB.",
            )

        # 🔒 检查总文件大小
        total_size += file_size
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload size exceeds limit. "
                f"Maximum total size is {MAX_TOTAL_SIZE / (1024 * 1024):.1f} MB, "
                f"but got {total_size / (1024 * 1024):.2f} MB.",
            )

        logger.info(f"⚙️ Processing file: {filename} ({file_size} bytes)")

        # 🔒 验证文件类型
        is_valid, error_msg = validate_file_type(content, file.filename)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type for '{file.filename}': {error_msg}",
            )

        # 使用统一的文件解析函数
        text = extract_text_from_file(content, file.filename)

        if text:
            combined_text += f"\n\n--- FILE: {file.filename} ---\n{text}"

    file_id = f"session_{uuid.uuid4().hex[:8]}"
    redis_client.setex(file_id, 3600, combined_text)
    logger.info(
        f"✅ Upload successful: {len(files)} files, total {total_size / (1024 * 1024):.2f} MB"
    )
    return {"status": "success", "file_id": file_id, "file_count": len(files)}


@app.post("/chat", dependencies=[Depends(verify_token)])
@limiter.limit("30/minute")
async def chat_endpoint(
    request: Request, body: ChatRequest, notion_service=Depends(get_notion_service)
):
    """聊天接口"""
    context = ""
    source_hint = ""
    if body.file_id:
        cached_text = redis_client.get(body.file_id)
        if cached_text:
            context = cached_text[:20000]
            source_hint = "【Current Uploaded File】"

    system_instruction = """
    You are Exocortex, an AI assistant.
    If you use the audio tool, you MUST output the tag exactly: [AUDIO_URL: filename.mp3]
    """
    final_query = f"{system_instruction}\n\n{source_hint}:\n{context}\n\n【User Query】:\n{body.query}"

    async def event_generator():
        # 🔥 获取动态模型实例
        model_instance = get_model(body.model_name)

        # server.py 中的 event_generator 内部
        config = {
            "configurable": {
                "thread_id": body.thread_id,
                "model": model_instance,
                "notion_service": notion_service,  # 🔥 注入实例
                "db_ids": {  # 🔥 注入 ID 映射
                    "Tech": current_config.DB_TECH_ID,
                    "Humanities": current_config.DB_HUMANITIES_ID,
                    "Spanish": current_config.DB_SPANISH_ID,
                    "General": current_config.DB_TECH_ID,
                },
            }
        }

        inputs = {"messages": [HumanMessage(content=final_query)]}
        async for event in graph.astream_events(inputs, config=config, version="v1"):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield content

    return StreamingResponse(event_generator(), media_type="text/plain")


@app.post("/archive", dependencies=[Depends(verify_token)])
@limiter.limit("5/minute")
async def archive_endpoint(
    request: Request,
    req: ArchiveRequest,
    background_tasks: BackgroundTasks,
    vector_store=Depends(get_vector_store),
    notion_service=Depends(get_notion_service),
):
    """归档接口"""
    if not redis_client.exists(req.file_id):
        raise HTTPException(status_code=404, detail="Session expired.")

    background_tasks.add_task(
        archive_session,
        req.file_id,
        req.summary,
        req.thread_id,
        redis_client,
        vector_store,
        notion_service,
    )
    return {"status": "queued"}


@app.post("/sync_notion")
async def sync_notion(
    notion_service=Depends(get_notion_service),
    vector_store=Depends(get_vector_store),
    config=Depends(get_config),
):
    """手动触发同步的 API 接口（支持增量同步和去重）"""
    db_id = config.DB_SPANISH_ID

    if not db_id:
        logger.error("❌ DB_SPANISH_ID 未配置")
        return {"status": "error", "message": "DB_SPANISH_ID not found in Settings"}

    result = sync_notion_database(
        db_id=db_id,
        notion_token=config.NOTION_TOKEN,
        vector_store=vector_store,
        domain="Spanish",
    )
    return result


# --- 启动事件 ---
@app.on_event("startup")
async def startup_event():
    """应用启动时注册后台任务"""
    config = get_config()
    asyncio.create_task(
        auto_sync_scheduler(
            db_id=config.DB_SPANISH_ID,
            notion_token=config.NOTION_TOKEN,
            get_vector_store_func=get_vector_store,
            get_config_func=get_config,
        )
    )
    logger.info("🚀 [System] 增量同步任务已挂载，启动30秒后开始第一次同步，之后每24小时自动同步。")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.4.0-Refactored"}


@app.get("/csrf-token")
async def get_csrf_token_endpoint():
    return {"csrf_token": generate_csrf_token()}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
