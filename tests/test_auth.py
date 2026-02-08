"""
tests/test_auth.py
Auth 单元测试
"""

import pytest
from fastapi import HTTPException

from middleware.auth import verify_token


# 使用 pytest-asyncio 运行异步测试
@pytest.mark.asyncio
async def test_verify_valid_token():
    class MockConfig:
        API_SECRET = "test_secret"

    class MockCreds:
        credentials = "test_secret"

    # ✅ 修复点：await 异步函数
    await verify_token(MockCreds(), MockConfig())


@pytest.mark.asyncio
async def test_verify_invalid_token():
    class MockConfig:
        API_SECRET = "test_secret"

    class MockCreds:
        credentials = "wrong_secret"

    # ✅ 修复点：await 异步函数
    with pytest.raises(HTTPException):
        await verify_token(MockCreds(), MockConfig())
