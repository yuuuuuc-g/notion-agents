"""
server.py
Backend API 入口 (FastAPI)
包含: Redis 缓存, Notion 归档, 完整鉴权
重构内容：引入配置注入模式 (Dependency Injection) 与 动态模型注入
"""

import os
import tempfile
import uuid
from functools import lru_cache
from io import BytesIO
from typing import List, Optional

# 文件解析库
import ebooklib
import magic  # MIME 类型验证
import pdfplumber
import redis
import uvicorn
from bs4 import BeautifulSoup
from ebooklib import epub

# FastAPI 核心组件
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    Security,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

# 🔒 CSRF 保护
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

# 🔒 限流中间件
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.sessions import SessionMiddleware

# Agent 核心
from agent.agent_graph import graph
from config.settings import SETTINGS  # 仅在工厂函数中使用

# 🔥 引入 Notion 模块
from notion.block_builder import markdown_to_blocks

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
from vector.vector_store import LevelChunkVectorStore  # noqa: E402 导入我们刚改好的类


@lru_cache()
def get_vector_store():
    """
    向量库工厂：确保全局只初始化一个向量库实例。
    """
    return LevelChunkVectorStore()


from notion.notion_ops import NotionService  # noqa: E402 确保导入新类


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
    version="2.3.0",
)

# --- 🔒 配置限流器 ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 🔒 配置 Session 与 CSRF ---
current_config = get_config()
app.add_middleware(
    SessionMiddleware, secret_key=current_config.API_SECRET or "fallback-secret"
)
csrf_serializer = URLSafeTimedSerializer(current_config.API_SECRET or "fallback-secret")

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

# --- 4. 安全鉴权 (注入模式) ---
security_scheme = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    config=Depends(get_config),
):
    """验证 Bearer Token"""
    token = credentials.credentials
    if token != config.API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def generate_csrf_token() -> str:
    """生成 CSRF token"""
    return csrf_serializer.dumps("csrf-protection", salt="csrf-salt")


def verify_csrf_token(token: str, max_age: int = 3600) -> bool:
    """验证 CSRF token"""
    try:
        csrf_serializer.loads(token, salt="csrf-salt", max_age=max_age)
        return True
    except (BadSignature, SignatureExpired):
        return False


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


# --- 7. 安全与文件处理函数 (保持不变) ---
def validate_file_type(content: bytes, filename: str) -> tuple[bool, str]:
    try:
        mime = magic.from_buffer(content, mime=True)
        allowed_types = {
            "application/pdf": [".pdf"],
            "text/plain": [".txt", ".md"],
            "application/epub+zip": [".epub"],
            "application/zip": [".epub"],
        }
        if mime not in allowed_types:
            return False, f"File type '{mime}' not allowed."
        extension = os.path.splitext(filename.lower())[1]
        if extension not in allowed_types[mime]:
            return False, f"Extension '{extension}' doesn't match MIME."
        return True, ""
    except Exception as e:
        logger.error(f"MIME validation error: {e}")
        return False, "Validation failed."


def extract_pdf_text(file_bytes: bytes) -> str:
    """
    使用 pdfplumber 替换 pypdf，解决学术 PDF 截断问题。
    """
    text_list = []
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            logger.info(f"📑 PDF opened: {len(pdf.pages)} pages detected.")
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text_list.append(page_text)

        full_text = "\n\n".join(text_list)
        logger.info(f"✅ Extraction complete. Total characters: {len(full_text)}")
        return full_text
    except Exception as e:
        logger.error(f"❌ pdfplumber Error: {e}")
        return ""


def extract_text_from_epub(file_bytes: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=".epub") as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file.flush()
            book = epub.read_epub(tmp_file.name)
            chapters = []
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), "html.parser")
                    chapters.append(soup.get_text())
            return "\n".join(chapters)
    except Exception as e:
        logger.error(f"❌ EPUB Error: {e}")
        return ""


def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("gbk", errors="ignore")


# --- 8. 后台任务逻辑 ---


def background_archive_task(
    file_id: str, summary: str, thread_id: str, vector_store, notion_service
):
    logger.info(f"⏳ [Background] Archiving session {file_id}...")
    full_text = redis_client.get(file_id)
    if not full_text:
        logger.error("❌ Context not found.")
        return

    try:
        # 1. Notion 归档
        content_blocks = markdown_to_blocks(full_text)
        page_title = f"Exocortex Archive: {summary[:50]}..."
        response = notion_service.create_page(title=page_title, children=content_blocks)
        notion_page_id = response.get("id")

        # 2. 🔥 修正：使用传入的 vector_store 实例存储记忆
        success = vector_store.add_memory(
            page_id=notion_page_id,
            text=full_text,
            title=page_title,
            domain="General",
            metadata={"summary": summary},
        )
        if success:
            logger.info("✅ Indexed to ChromaDB using Dependency Injection!")
    except Exception:
        logger.exception("❌ Error during archiving")


# ============================
# 🚀 核心接口 (Endpoints)
# ============================


@app.post("/upload")
@limiter.limit("10/minute")
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(status_code=413, detail="Too many files.")

    combined_text = ""
    for file in files:
        content = await file.read()
        filename = file.filename.lower()
        logger.info(f"⚙️ Processing file: {filename} ({len(content)} bytes)")  # 👈 强制打印

        text = ""
        if filename.endswith(".pdf"):
            text = extract_pdf_text(content)
        elif filename.endswith(".epub"):
            text = extract_text_from_epub(content)
        elif filename.endswith((".txt", ".md")):  # 优化写法
            text = extract_text_from_txt(content)

        # 调试：不管有没有 text，都看看到底解析出多少
        logger.info(f"📊 Result for {filename}: {len(text) if text else 0} chars")

        if text:
            combined_text += f"\n\n--- FILE: {file.filename} ---\n{text}"

    file_id = f"session_{uuid.uuid4().hex[:8]}"
    redis_client.setex(file_id, 3600, combined_text)
    return {"status": "success", "file_id": file_id, "file_count": len(files)}


@app.post("/chat", dependencies=[Depends(verify_token)])
@limiter.limit("30/minute")
async def chat_endpoint(
    request: Request, body: ChatRequest, notion_service=Depends(get_notion_service)
):
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
    if not redis_client.exists(req.file_id):
        raise HTTPException(status_code=404, detail="Session expired.")

    background_tasks.add_task(
        background_archive_task,
        req.file_id,
        req.summary,
        req.thread_id,
        vector_store,
        notion_service,
    )
    return {"status": "queued"}


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "2.3.0-DI"}


@app.get("/csrf-token")
async def get_csrf_token():
    return {"csrf_token": generate_csrf_token()}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
