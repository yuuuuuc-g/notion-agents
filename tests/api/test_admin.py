"""
tests/api/test_admin.py
测试管理后台接口 (Notion同步)
适配 v3.4 架构: 使用 Dependency Override
"""
from unittest.mock import AsyncMock

import pytest

from api.dependencies import get_sync_service


@pytest.mark.api
def test_sync_notion_success(test_client):
    """测试同步触发成功"""

    # 1. 创建一个假的 SyncService
    mock_service = AsyncMock()
    mock_service.sync_database.return_value = {
        "status": "success",
        "synced_count": 10,
        "stats": {"new": 10, "updated": 0},
    }

    # 2. 覆盖依赖：当路由请求 get_sync_service 时，给它我们的假服务
    # test_client.app 引用的是 server.py 里的 app 对象
    test_client.app.dependency_overrides[get_sync_service] = lambda: mock_service

    try:
        response = test_client.post("/sync_notion")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["stats"]["new"] == 10

        # 验证 service 方法确实被调用了
        mock_service.sync_database.assert_called_once()

    finally:
        # 3. 清理：测试完后一定要还原，否则会影响其他测试
        del test_client.app.dependency_overrides[get_sync_service]


@pytest.mark.api
def test_sync_notion_no_config(test_client):
    """测试配置缺失的情况"""
    from api.dependencies import get_settings
    from config.settings import Settings

    # 创建一个没有 DB ID 的配置
    # 注意：Settings 验证较严，我们mock它或者临时修改属性
    # 这里我们直接 override 依赖
    mock_settings = Settings(
        API_SECRET="test" * 8,
        NOTION_TOKEN="t",
        SILICON_KEY="s",
        DB_SPANISH_ID="",  # 空 ID
    )

    test_client.app.dependency_overrides[get_settings] = lambda: mock_settings

    try:
        response = test_client.post("/sync_notion")
        assert response.status_code == 200
        assert response.json()["status"] == "error"
        assert "No DB ID" in response.json()["message"]
    finally:
        del test_client.app.dependency_overrides[get_settings]
