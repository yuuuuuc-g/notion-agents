"""
tests/middleware/test_validation_error.py
专门测试参数验证错误 (422)，补齐 error_handler 覆盖率
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from middleware.error_handler import register_exception_handlers


class Item(BaseModel):
    name: str
    price: int


def create_app():
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/items")
    def create_item(item: Item):
        return item

    return app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_validation_error(client):
    # 发送非法数据（缺少 price，name 是 int 这种类型错误）
    response = client.post("/items", json={"name": 123})

    assert response.status_code == 422
    data = response.json()

    # 验证 error_handler 转换后的格式
    assert data["code"] == "VALIDATION_ERROR"
    assert "details" in data
    assert "errors" in data["details"]
    # 确保 Pydantic 的错误信息被捕获
    assert len(data["details"]["errors"]) > 0
