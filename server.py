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

# 引入向量存储模块
from vector.vector_store import add_memory, search_memory

# 文件解析库
from pypdf import PdfReader
from ebooklib import epub
from bs4 import BeautifulSoup

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


# --- 6. 辅助函数 ---
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
async def upload_files(files: List[UploadFile] = File(...)):
    logger.info(f"📂 Receiving {len(files)} files...")
    combined_text = ""

    for file in files:
        content = await file.read()
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
async def chat_endpoint(request: ChatRequest, req: Request):
    # --- 1. 准备上下文 (RAG 逻辑保持不变) ---
    context = ""
    source_hint = ""

    # (这里保留你原本的 Redis 和 RAG 检索逻辑，不需要变)
    if request.file_id:
        try:
            cached_text = redis_client.get(request.file_id)
            if cached_text:
                context = cached_text[:20000]
                source_hint = "【Current Uploaded File】"
        except Exception:
            pass

    if not context:
        # RAG 检索逻辑... (保持你之前的代码不变)
        try:
            search_result = search_memory(request.query)
            if search_result["match"]:
                full_doc = search_result["metadata"]["content"]
                context = full_doc[:15000]
                page_title = search_result.get("title", "Unknown")
                source_hint = f"【Long-term Memory: {page_title}】"
        except Exception:
            pass

    # --- 2. 组装 Prompt (Prompt 逻辑保持不变) ---
    # 记得把 file_id 塞进去，为了让 Agent 能用工具
    system_instruction = f"""
You are Exocortex.
=== CONTEXT DATA ===
Current Uploaded File ID: {request.file_id if request.file_id else "None"}
(If user asks to save/archive, use `save_current_file_to_notion` with this ID).
====================
"""
    if context:
        final_query = f"{system_instruction}\n\n{source_hint}:\n{context}\n\n【User Query】:\n{request.query}"
    else:
        final_query = f"{system_instruction}\n\n【User Query】:\n{request.query}"

    # --- 3. 🔥 定义流式生成器 (核心修改) ---
    async def event_generator():
        config = {"configurable": {"thread_id": request.thread_id}}
        inputs = {"messages": [HumanMessage(content=final_query)]}

        # 使用 astream_events 监听所有事件 (v1 版本 API)
        # 这样我们可以区分：是工具在跑，还是 AI 在说话
        async for event in graph.astream_events(inputs, config=config, version="v1"):
            kind = event["event"]

            # 🟢 Case A: 模型正在生成文本 (流式输出)
            if kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    # 直接发送文本片段
                    yield content

            # 🟡 Case B: 工具开始调用 (可选：发个信号告诉前端我在干活)
            elif kind == "on_tool_start":
                yield " 🛠️ [Thinking...] "

            # 🔴 Case C: 工具调用结束
            elif kind == "on_tool_end":
                yield " ✅ "

    # --- 4. 返回流式响应 ---
    # media_type="text/plain" 表示直接返回纯文本流，前端处理起来最简单
    return StreamingResponse(event_generator(), media_type="text/plain")


# 🔥🔥🔥 新增归档接口 🔥🔥🔥
@app.post("/archive", dependencies=[Depends(verify_token)])
async def archive_endpoint(req: ArchiveRequest, background_tasks: BackgroundTasks):
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


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
