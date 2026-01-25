"""
tests/middleware/test_error_handler_final.py
测试全局异常处理器的各个分支
版本：Final (Safe Objects) - 使用真实对象替代 Mock 防止 Crash
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from middleware.error_handler import BusinessException, register_exception_handlers


# ✅ 关键修复：定义一个简单的 Limit 类，而不是使用 MagicMock
# 这样可以避免 slowapi 内部 isinstance 检查或属性访问导致的崩溃
class MockLimit:
    def __init__(self, limit_value: str, error_message: str):
        self.limit = limit_value
        self.error_message = error_message

    # 某些版本的 slowapi 可能会尝试 str() 这个对象
    def __str__(self):
        return self.limit


def create_error_app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/business_error")
    def raise_business():
        raise BusinessException(message="Invalid Operation", code="BIZ_001")

    @app.get("/value_error")
    def raise_value():
        raise ValueError("Unexpected math error")

    @app.get("/rate_limit")
    def raise_rate_limit():
        # ✅ 使用安全的对象初始化异常
        # 这里的参数顺序和属性名严格对齐 slowapi 源码
        limit_obj = MockLimit(
            limit_value="5/minute", error_message="Rate limit exceeded"
        )
        raise RateLimitExceeded(limit_obj)

    return app


@pytest.fixture
def error_client():
    app = create_error_app()
    # raise_server_exceptions=False 允许我们收到 500/429 响应进行断言
    return TestClient(app, raise_server_exceptions=False)


def test_business_exception(error_client):
    response = error_client.get("/business_error")
    assert response.status_code == 400
    assert response.json()["code"] == "BIZ_001"


def test_general_exception(error_client):
    response = error_client.get("/value_error")
    assert response.status_code == 500
    data = response.json()
    assert data["code"] == "INTERNAL_ERROR"


def test_rate_limit_exception(error_client):
    response = error_client.get("/rate_limit")
    # 如果这里依然是 500，说明异常构造函数还在崩，但现在的 MockLimit 应该很稳
    assert response.status_code == 429
    data = response.json()
    assert data["code"] == "RATE_LIMIT_EXCEEDED"
