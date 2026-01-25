"""
tests/api/test_admin.py
测试 Admin 接口
"""
from unittest.mock import AsyncMock


def test_sync_notion_success(client, mock_container):
    # 1. 获取 Simple Mock 实例
    mock_sync = mock_container.sync_service()

    # 2. 🔥 关键修复：用 AsyncMock 替换掉实例上的真实方法
    # 这样我们才能设置 return_value 并进行断言
    mock_sync.sync_database = AsyncMock(return_value={"status": "success"})

    # Config
    mock_settings = mock_container.config()
    mock_settings.DB_SPANISH_ID = "mock-db-id"

    response = client.post("/api/admin/sync_notion")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_sync_notion_no_config(client, mock_container):
    mock_settings = mock_container.config()
    mock_settings.DB_SPANISH_ID = None

    response = client.post("/api/admin/sync_notion")
    assert response.status_code == 200
    assert response.json()["status"] == "error"
