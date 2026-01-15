"""
server.py
Backend API 入口 (FastAPI)
包含: Redis 缓存, Notion 归档, 完整鉴权
"""

import os
import re
import uvicorn
import uuid
import redis
import traceback
from typing import List, Optional
from io import BytesIO
import tempfile
import json

# FastAPI 核心组件
from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Depends,
    Security,
    status,
    UploadFile,
    File,
    BackgroundTasks,
)
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

# 🔒 限流中间件
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# 🔒 CSRF 保护
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# 引入向量存储模块
from vector.vector_store import add_memory, search_memory

# 文件解析库
from pypdf import PdfReader
from ebooklib import epub
from bs4 import BeautifulSoup
import magic  # MIME 类型验证

# Agent 核心
from agent.agent_graph import graph
from langchain_core.messages import HumanMessage
from config.settings import SETTINGS

# 🔥 引入 Notion 模块 (确保你已经更新了 notion_ops.py)
from notion.block_builder import markdown_to_blocks
from notion.notion_ops import create_notion_page

# 🔧 引入日志模块
from utils.logger import get_logger

logger = get_logger(__name__)

# --- 初始化 APP ---
app = FastAPI(
    title="Exocortex API",
    description="Backend service for Notion-Prism-React Agent",
    version="2.2.0",
)

# --- 🔒 配置限流器 ---
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- 🔒 配置 Session 中间件（CSRF 需要）---
app.add_middleware(
    SessionMiddleware, secret_key=SETTINGS.API_SECRET or "fallback-secret"
)

# --- 🔒 CSRF Token 生成器 ---
csrf_serializer = URLSafeTimedSerializer(SETTINGS.API_SECRET or "fallback-secret")

# --- 1. 配置 CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],  # Removed "*" wildcard
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
AUDIO_DIR = SETTINGS.AUDIO_DIR
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# --- 4. 安全鉴权 ---
security_scheme = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
):
    """验证 Bearer Token"""
    token = credentials.credentials
    if token != SETTINGS.API_SECRET:
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
    """
    验证 CSRF token
    max_age: token 有效期（秒），默认 1 小时
    """
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
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file
MAX_TOTAL_SIZE = 100 * 1024 * 1024  # 100MB total per request
MAX_FILES_COUNT = 10  # Maximum 10 files per upload


# --- 7. 安全函数 ---
def validate_file_type(content: bytes, filename: str) -> tuple[bool, str]:
    """
    验证文件的真实 MIME 类型（不仅检查扩展名）

    Returns:
        (is_valid: bool, error_message: str)
    """
    try:
        mime = magic.from_buffer(content, mime=True)

        # 允许的 MIME 类型及其对应的扩展名
        allowed_types = {
            "application/pdf": [".pdf"],
            "text/plain": [".txt", ".md"],
            "application/epub+zip": [".epub"],
            "application/zip": [".epub"],  # EPUB 有时被识别为 zip
        }

        if mime not in allowed_types:
            return False, f"File type '{mime}' not allowed. Allowed: PDF, TXT, EPUB, MD"

        # 验证扩展名与 MIME 类型匹配
        extension = os.path.splitext(filename.lower())[1]
        if extension not in allowed_types[mime]:
            return (
                False,
                f"File extension '{extension}' doesn't match MIME type '{mime}'",
            )

        return True, ""
    except Exception as e:
        logger.error(f"MIME validation error: {e}")
        return False, f"Unable to validate file type: {str(e)}"


# --- 8. 文件处理函数 ---
def extract_pdf_text(file_bytes: bytes) -> str:
    try:
        pdf_file = BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text = [page.extract_text() for page in reader.pages]
        return "\n".join(text)
    except Exception as e:
        logger.error(f"❌ PDF Error: {e}")
        return ""


def extract_text_from_epub(file_bytes: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=".epub") as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file.flush()
            book = epub.read_epub(tmp_file.name)
            chapters = []
            for item in book.get_items():
                if item.get_type() == epub.ITEM_DOCUMENT:
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


def extract_and_convert_paths(text: str, base_url: str) -> tuple[str, str | None]:
    audio_url = None
    clean_text = text
    match = re.search(
        r"generated_audio[\\/](audio_[a-f0-9]+\.mp3)", text, re.IGNORECASE
    )
    if match:
        filename = match.group(1)
        audio_url = f"{base_url}/audio/{filename}"
    return clean_text, audio_url


# --- 🏗️ 后台任务逻辑 (更新版) ---
def background_archive_task(file_id: str, summary: str, thread_id: str):
    logger.info(f"⏳ [Background] Archiving session {file_id}...")

    # 1. 从 Redis 取出完整原文
    full_text = redis_client.get(file_id)
    if not full_text:
        logger.error(f"❌ [Background] Failed: Context {file_id} expired or not found.")
        return

    try:
        # 2. 转 Blocks 并写入 Notion
        logger.info(
            f"   - Converting text to Notion blocks ({len(full_text)} chars)..."
        )
        content_blocks = markdown_to_blocks(full_text)

        page_title = f"Exocortex Archive: {summary[:50]}..."

        # 3. 写入 Notion
        response = create_notion_page(
            title=page_title, children=content_blocks, icon="💾"
        )
        notion_page_id = response.get("id")
        logger.info(f"✅ [Background] Saved to Notion! Page ID: {notion_page_id}")

        # 4. 🔥🔥🔥 新增：写入向量数据库 (ChromaDB + SQLite) 🔥🔥🔥
        logger.info(f"   - Indexing to Vector Store (Level-Chunk Strategy)...")
        success = add_memory(
            page_id=notion_page_id,  # 用 Notion 的 ID 作为父文档 ID，方便未来溯源
            text=full_text,
            title=page_title,
            domain="General",  # 这里以后可以做分类
            metadata={"summary": summary},
        )

        if success:
            logger.info(f"✅ [Background] Successfully indexed to ChromaDB!")
        else:
            logger.warning(f"⚠️ [Background] Vector indexing returned False.")

    except Exception as e:
        logger.exception("❌ [Background] Error during archiving")


# ============================
# 🚀 核心接口 (Endpoints)
# ============================


@app.post("/upload")
@limiter.limit("10/minute")  # 限制每分钟 10 次上传
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    logger.info(f"📂 Receiving {len(files)} files...")

    # 🔒 安全检查 1: 文件数量限制
    if len(files) > MAX_FILES_COUNT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Too many files. Maximum {MAX_FILES_COUNT} files allowed per upload.",
        )

    combined_text = ""
    total_size = 0

    for file in files:
        # 🔒 安全检查 2: 单个文件大小限制
        # Read file to check size (we need to read anyway for processing)
        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{file.filename}' exceeds {MAX_FILE_SIZE // (1024 * 1024)}MB limit. Size: {file_size // (1024 * 1024)}MB",
            )

        # 🔒 安全检查 3: 总大小限制
        total_size += file_size
        if total_size > MAX_TOTAL_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total upload size exceeds {MAX_TOTAL_SIZE // (1024 * 1024)}MB limit.",
            )

        logger.info(f"   📄 Processing '{file.filename}' ({file_size // 1024}KB)")

        # 🔒 安全检查 4: MIME 类型验证（防止恶意文件）
        is_valid, error_msg = validate_file_type(content, file.filename)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File '{file.filename}': {error_msg}",
            )

        filename = file.filename.lower()
        text = ""

        if filename.endswith(".pdf"):
            text = extract_pdf_text(content)
        elif filename.endswith(".epub"):
            text = extract_text_from_epub(content)
        elif filename.endswith(".txt") or filename.endswith(".md"):
            text = extract_text_from_txt(content)

        if text:
            combined_text += f"\n\n--- FILE: {file.filename} ---\n{text}"

    file_id = f"session_{uuid.uuid4().hex[:8]}"

    try:
        redis_client.setex(file_id, 3600, combined_text)
        logger.info(
            f"💾 Stored context to Redis: {file_id} (Length: {len(combined_text)})"
        )
    except Exception as e:
        logger.error(f"❌ Redis Write Error: {e}")
        return {"status": "error", "message": "Cache failed"}

    return {
        "status": "success",
        "file_count": len(files),
        "file_id": file_id,
        "message": "Content cached for 1 hour.",
    }


# 🔥 修改 endpoint 定义，不再声明 response_model (因为现在返回流)
@app.post("/chat", dependencies=[Depends(verify_token)])
@limiter.limit("30/minute")  # 限制每分钟 30 次对话请求
async def chat_endpoint(request: Request, body: ChatRequest):  # 🔥 交换位置并改名
    # --- 1. 准备上下文 ---
    # 因为改了名，所以要把下面代码里用到的 request 换成 body
    context = ""
    source_hint = ""

    # 注意：这里原来是用 request.file_id，现在要改成 body.file_id
    if body.file_id:
        try:
            cached_text = redis_client.get(body.file_id)
            if cached_text:
                context = cached_text[:20000]
                source_hint = "【Current Uploaded File】"
        except Exception:
            pass

    # --- 2. 组装 Prompt ---
    # 提示词中加入对音频标记的要求

    system_instruction = f"""
    You are Exocortex, an AI assistant.
    Current Context File ID:  {body.file_id if body.file_id else "None"}
    If you use the audio tool, you MUST output the tag exactly: [AUDIO_URL: filename.mp3]
    """
    if context:
        final_query = f"{system_instruction}\n\n{source_hint}:\n{context}\n\n【User Query】:\n{body.query}"
    else:
        final_query = f"{system_instruction}\n\n【User Query】:\n{body.query}"

    # --- 3. 定义流式生成器 ---
    async def event_generator():
        # 注意：这里原来是 request.thread_id，现在改成 body.thread_id
        config = {"configurable": {"thread_id": body.thread_id}}
        inputs = {"messages": [HumanMessage(content=final_query)]}
        
        async for event in graph.astream_events(inputs, config=config, version="v1"):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield content

    return StreamingResponse(event_generator(), media_type="text/plain")


# 🔥🔥🔥 新增归档接口 🔥🔥🔥
@app.post("/archive", dependencies=[Depends(verify_token)])
@limiter.limit("5/minute")  # 限制每分钟 5 次归档请求
async def archive_endpoint(
    request: Request, req: ArchiveRequest, background_tasks: BackgroundTasks
):
    # 检查 Redis 里还有没有
    if not redis_client.exists(req.file_id):
        raise HTTPException(status_code=404, detail="Session expired, cannot archive.")

    # 启动后台任务
    background_tasks.add_task(
        background_archive_task, req.file_id, req.summary, req.thread_id
    )

    return {"status": "queued", "message": "Archiving started in background."}


# --- 健康检查 ---
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Exocortex Brain (v2.2 Secured)"}


# --- 🔒 CSRF Token 端点 ---
@app.get("/csrf-token")
async def get_csrf_token():
    """
    获取 CSRF token（用于前端表单提交）
    注意：此端点不需要认证，因为 token 本身不敏感
    """
    token = generate_csrf_token()
    return {"csrf_token": token}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
