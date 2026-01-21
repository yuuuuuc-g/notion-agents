"""
tests/unit/test_file_parser.py
文件解析服务单元测试
"""
import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from services.file_parser import (
    extract_text_from_upload_file,
    validate_and_read_file,
    validate_filename,
)


@pytest.mark.asyncio
async def test_validate_filename():
    """测试文件名安全"""
    validate_filename("safe.pdf")
    with pytest.raises(HTTPException):
        validate_filename("../unsafe.pdf")


@pytest.mark.asyncio
async def test_extract_text_from_txt():
    """测试 TXT 提取"""
    content = b"Hello World"
    file = UploadFile(filename="test.txt", file=io.BytesIO(content))

    with patch(
        "services.file_parser.validate_and_read_file", new_callable=AsyncMock
    ) as mock_read:
        mock_read.return_value = (".txt", content)
        result = await extract_text_from_upload_file(file)
        assert result == "Hello World"


@pytest.mark.asyncio
async def test_extract_pdf_js_detection():
    """测试 PDF 恶意代码检测"""
    malicious_content = b"%PDF-1.4 ... /JavaScript (alert(1)) ..."
    file = UploadFile(filename="bad.pdf", file=io.BytesIO(malicious_content))

    # ✅ 修复点：正确 Patch 'services.file_parser.magic'
    # 这样内部调用的 magic.from_buffer 才会变成我们想要的返回值
    with patch("services.file_parser.magic") as mock_magic:
        mock_magic.from_buffer.return_value = "application/pdf"

        with pytest.raises(HTTPException) as exc:
            await validate_and_read_file(file)

        assert exc.value.status_code == 400
        assert "恶意" in exc.value.detail or "Malicious" in exc.value.detail
