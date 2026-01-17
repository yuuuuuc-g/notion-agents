"""
services/file_parser.py
文件解析服务 - 提取各种文件格式的文本内容
"""
import logging
import tempfile
import warnings
from io import BytesIO
from typing import Tuple

import ebooklib
import magic
import pdfplumber
from bs4 import BeautifulSoup
from ebooklib import epub

from utils.logger import get_logger

logger = get_logger(__name__)


def validate_file_type(content: bytes, filename: str) -> Tuple[bool, str]:
    """
    验证文件类型和扩展名是否匹配

    Args:
        content: 文件内容（字节）
        filename: 文件名

    Returns:
        (是否有效, 错误信息)
    """
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
        import os

        extension = os.path.splitext(filename.lower())[1]
        expected_extensions = allowed_types[mime]
        if extension not in expected_extensions:
            return False, f"Extension '{extension}' doesn't match MIME '{mime}'."
        return True, ""
    except Exception as e:
        logger.error(f"MIME validation error: {e}")
        return False, "Validation failed."


def extract_pdf_text(file_bytes: bytes) -> str:
    """
    从 PDF 文件中提取文本内容
    使用 pdfplumber 替换 pypdf，解决学术 PDF 截断问题。

    Args:
        file_bytes: PDF 文件内容（字节）

    Returns:
        提取的文本内容
    """
    # 🔇 抑制 pdfplumber 的 FontBBox 警告（这些警告不影响文本提取）
    warnings.filterwarnings("ignore", message=".*FontBBox.*")
    # 抑制 pdfminer 的警告日志
    pdfminer_logger = logging.getLogger("pdfminer")
    original_level = pdfminer_logger.level
    pdfminer_logger.setLevel(logging.ERROR)

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
    finally:
        # 恢复 pdfminer 的日志级别
        pdfminer_logger.setLevel(original_level)


def extract_text_from_epub(file_bytes: bytes) -> str:
    """
    从 EPUB 文件中提取文本内容

    Args:
        file_bytes: EPUB 文件内容（字节）

    Returns:
        提取的文本内容
    """
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
    """
    从文本文件中提取内容（支持 UTF-8 和 GBK 编码）

    Args:
        file_bytes: 文本文件内容（字节）

    Returns:
        提取的文本内容
    """
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("gbk", errors="ignore")


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """
    根据文件扩展名自动选择解析方法

    Args:
        file_bytes: 文件内容（字节）
        filename: 文件名

    Returns:
        提取的文本内容
    """
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        return extract_pdf_text(file_bytes)
    elif filename_lower.endswith(".epub"):
        return extract_text_from_epub(file_bytes)
    elif filename_lower.endswith((".txt", ".md")):
        return extract_text_from_txt(file_bytes)
    else:
        logger.warning(f"Unsupported file type: {filename}")
        return ""
