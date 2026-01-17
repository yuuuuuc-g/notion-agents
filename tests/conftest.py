from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from server import app, get_config, get_notion_service


# 定义一个伪造的配置类
class MockConfig:
    API_SECRET = "test-secret"
    SILICON_KEY = "mock-key"
    NOTION_TOKEN = "mock-token"
    DB_TECH_ID = "mock-db"
    DB_HUMANITIES_ID = "mock-db"
    DB_SPANISH_ID = "mock-db"
    AUDIO_DIR = "./tests/audio"


@pytest.fixture
def mock_notion_service():
    service = MagicMock()
    service.create_page.return_value = {"id": "test-page-id"}
    return service


@pytest.fixture
def test_client(mock_notion_service):
    """
    通过 dependency_overrides 注入测试专用配置和 Service
    """
    # 覆盖配置：确保 API_SECRET 永远是 test-secret
    app.dependency_overrides[get_config] = lambda: MockConfig()
    # 覆盖 Notion 服务
    app.dependency_overrides[get_notion_service] = lambda: mock_notion_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    # 这里的 token 必须和 MockConfig.API_SECRET 一致
    return {"Authorization": "Bearer test-secret"}
