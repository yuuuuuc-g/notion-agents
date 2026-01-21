"""
tests/test_auth.py
Auth 单元测试
"""

import pytest
from fastapi import HTTPException

from middleware.auth import generate_csrf_token, verify_csrf_token, verify_token


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


def test_csrf_flow():
    token = generate_csrf_token()
    assert verify_csrf_token(token) is True


def test_csrf_expired():
    token = generate_csrf_token()
    # 强制过期检查
    # 注意：verify_csrf_token 内部是同步的，可以直接调用
    # max_age=0 理论上应该立即使 token 过期
    # 但为了稳妥，我们可以让它稍微睡一会或者 mock 时间，这里简单处理
    assert verify_csrf_token(token, max_age=-1) is False
