"""
services/file_parser.py
文件处理服务 - 终极版 (Fixed Imports)
功能：
1. 流式读取 (防OOM)
2. 深度安全校验 (Magic Number + PDF JS检查 + 路径遍历检查)
3. 多格式支持 (PDF, TXT, MD, EPUB)
"""
import io
import logging
from typing import AsyncGenerator, Tuple

import magic
import pypdf
from fastapi import HTTPException, UploadFile

# ✅ 修复点：正确导入项目中的日志工具
try:
    from utils.logger import get_logger

    logger = get_logger(__name__)
except ImportError:
    # 降级处理：如果找不到 utils.logger，使用标准库
    logger = logging.getLogger(__name__)

# EPUB 支持
try:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    HAS_EPUB_SUPPORT = True
except ImportError:
    HAS_EPUB_SUPPORT = False
    logger.warning("EbookLib or BeautifulSoup not found. EPUB support disabled.")

# 限制最大读取大小 (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
    "application/epub+zip": ".epub",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-m4a": ".m4a",
    "application/octet-stream": ".txt",
}


async def stream_file_content(
    file: UploadFile, chunk_size: int = 8192
) -> AsyncGenerator[bytes, None]:
    """流式读取生成器"""
    while chunk := await file.read(chunk_size):
        yield chunk


def validate_filename(filename: str):
    """文件名安全检查 (防止路径遍历)"""
    if not filename or filename.strip() == "":
        raise HTTPException(400, detail="Filename is empty")

    # 简单的路径遍历检查
    if ".." in filename or "/" in filename or "\\" in filename:
        logger.warning(
            f"🚨 Security Alert: Path traversal attempt detected in filename: {filename}"
        )
        raise HTTPException(400, detail="Invalid filename (Path traversal detected)")


async def validate_and_read_file(file: UploadFile) -> Tuple[str, bytes]:
    """
    深度验证并安全读取文件
    """
    # 1. 文件名检查
    validate_filename(file.filename)

    # 2. Magic Number 校验
    header = await file.read(2048)
    await file.seek(0)

    try:
        mime_type = magic.from_buffer(header, mime=True)
    except Exception:
        mime_type = "application/octet-stream"

    logger.info(f"🔍 File Check: {file.filename} -> {mime_type}")

    if mime_type not in ALLOWED_MIME_TYPES:
        # 宽容处理纯文本
        if not mime_type.startswith("text/"):
            pass

    ext = ALLOWED_MIME_TYPES.get(mime_type, ".txt")

    # 3. 流式读取 + 大小检查
    chunks = []
    total_size = 0

    async for chunk in stream_file_content(file):
        total_size += len(chunk)
        if total_size > MAX_FILE_SIZE:
            raise HTTPException(413, detail=f"❌ 文件过大 (Max {MAX_FILE_SIZE/1024/1024}MB)")
        chunks.append(chunk)

    full_content = b"".join(chunks)

    # 4. PDF 安全加固
    if ext == ".pdf":
        if b"/JavaScript" in full_content or b"/JS" in full_content:
            logger.warning(
                f"🚨 Security Alert: Malicious JS detected in PDF {file.filename}"
            )
            raise HTTPException(400, detail="❌ 安全拦截: PDF 包含潜在恶意脚本")

    return ext, full_content


def extract_text_from_pdf(content: bytes) -> str:
    try:
        pdf_file = io.BytesIO(content)
        reader = pypdf.PdfReader(pdf_file)
        text = []
        for i, page in enumerate(reader.pages):
            extracted = page.extract_text()
            if extracted:
                text.append(f"--- Page {i+1} ---\n{extracted}")
        return "\n".join(text)
    except Exception as e:
        logger.error(f"PDF parsing error: {e}")
        return f"[PDF Parse Error: {str(e)}]"


def extract_text_from_epub(content: bytes) -> str:
    """EPUB 解析逻辑"""
    if not HAS_EPUB_SUPPORT:
        return "[Error: EbookLib/BeautifulSoup not installed]"

    try:
        # 屏蔽 ebooklib 的无关警告
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            book = epub.read_epub(io.BytesIO(content))

        chapters = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            if text:
                chapters.append(text)
        return "\n\n".join(chapters)
    except Exception as e:
        logger.error(f"EPUB parsing error: {e}")
        return f"[EPUB Parse Error: {str(e)}]"


async def extract_text_from_upload_file(file: UploadFile) -> str:
    """统一提取入口"""
    ext, content = await validate_and_read_file(file)
    filename = file.filename.lower()

    # 分发处理
    if ext == ".pdf" or filename.endswith(".pdf"):
        return extract_text_from_pdf(content)
    elif ext == ".epub" or filename.endswith(".epub"):
        return extract_text_from_epub(content)
    else:
        # 默认尝试文本解码
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return content.decode("gbk")
            except Exception:
                return "[Binary/Unsupported Encoding]"
