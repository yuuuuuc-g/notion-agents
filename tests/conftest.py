"""
tests/conftest.py
Global test fixtures for Biobrain test suite.
✅ 最终架构版：使用 Fake (Simple Classes) 彻底解决 FastAPI 序列化和 Async Loop 冲突
"""

import os
from typing import Dict, Generator, List
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

# 1. 设置测试环境变量
os.environ["ENVIRONMENT"] = "testing"
os.environ["API_SECRET"] = "test-secret-key-must-be-long-enough-32chars"
os.environ["NOTION_TOKEN"] = "mock-notion-token"
os.environ["SILICON_KEY"] = "mock-silicon-key"
os.environ["DB_SPANISH_ID"] = "mock-spanish-db"

# 2. 导入依赖
from api.dependencies import (  # noqa: E402
    get_archive_service,
    get_audio_service,
    get_cache_wrapper,
    get_chat_service,
    get_notion_service,
    get_redis,
    get_settings,
    get_sync_service,
    get_vector_store,
)
from config.settings import Settings  # noqa: E402
from server import app  # noqa: E402

# =============================================================================
# ✅ Simple Mock Classes (Fake 模式) - 修正了方法名
# =============================================================================


class SimpleNotionMock:
    """Notion Service Fake"""

    def __init__(self):
        self.create_page_called = False

    def create_page(self, title: str, children: List[Dict], **kwargs) -> Dict:
        self.create_page_called = True
        return {"id": "mock-page-id", "title": title}

    def fetch_database_content(self, db_id: str, **kwargs) -> List[Dict]:
        return []


class SimpleVectorMock:
    """Vector Store Fake"""

    def __init__(self):
        self.memories = {}

    def add_memory(self, page_id: str, text: str, **kwargs) -> bool:
        self.memories[page_id] = text
        return True

    # 兼容旧接口
    def search_memory(self, query_text: str, **kwargs) -> Dict:
        return {"match": False, "results": []}

    # 兼容新接口
    def search_with_context(self, query: str, **kwargs) -> Dict:
        return {"match": False, "results": []}

    def page_exists(self, page_id: str) -> bool:
        return page_id in self.memories

    def delete_page(self, page_id: str) -> bool:
        return True


class SimpleChatServiceMock:
    """Chat Service Fake"""

    async def chat(self, message: str, **kwargs) -> Dict:
        return {"response": "Mock response"}

    # 🔥 修正方法名：stream_chat -> stream_response
    async def stream_response(self, query: str, **kwargs):
        yield "Hello"
        yield " World"


class SimpleSyncServiceMock:
    """Sync Service Fake"""

    # 🔥 修正方法名：sync_all_pages -> sync_database
    async def sync_database(self, db_id: str, **kwargs) -> Dict:
        return {
            "status": "success",
            "synced_count": 0,
            "message": "Mock sync completed",
        }


class SimpleAudioServiceMock:
    """Audio Service Fake"""

    async def generate_audio_file(self, text: str, **kwargs) -> str:
        return "/mock/path/to/audio.mp3"


class SimpleArchiveServiceMock:
    """Archive Service Fake"""

    # 🔥 修正方法名：archive_file -> archive_session
    async def archive_session(
        self, file_id: str, summary: str, thread_id: str, **kwargs
    ) -> Dict:
        return {
            "status": "success",
            "notion_id": "mock-id",
            "notion_url": "http://mock",
        }


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def mock_settings() -> Settings:
    return Settings(
        ENVIRONMENT="testing",
        DEBUG=True,
        API_SECRET="test-secret-key-must-be-long-enough-32chars",
        SILICON_KEY="mock-silicon-key",
        SILICON_BASE_URL="https://api.siliconflow.cn/v1",
        NOTION_TOKEN="mock-notion-token",
        DB_TECH_ID="mock-tech-db",
        DB_HUMANITIES_ID="mock-humanities-db",
        DB_SPANISH_ID="mock-spanish-db",
        AUDIO_DIR="./tests/fixtures/audio",
        TTS_RATE="-10%",
        USE_LOCAL_NANOGPT=False,
    )


# 实例化 Fake 对象
@pytest.fixture
def mock_notion_service():
    return SimpleNotionMock()


@pytest.fixture
def mock_vector_store():
    return SimpleVectorMock()


@pytest.fixture
def mock_chat_service():
    return SimpleChatServiceMock()


@pytest.fixture
def mock_sync_service():
    return SimpleSyncServiceMock()


@pytest.fixture
def mock_audio_service():
    return SimpleAudioServiceMock()


@pytest.fixture
def mock_archive_service():
    return SimpleArchiveServiceMock()


@pytest.fixture
def mock_redis() -> Mock:
    mock = Mock()
    mock.ping.return_value = True
    return mock


@pytest.fixture
def mock_cache_wrapper() -> Mock:
    cache = Mock()
    cache.exists.return_value = True  # 默认存在，防止 404
    cache.get.return_value = "Mock Content"
    cache.setex.return_value = True
    return cache


@pytest.fixture
def mock_container(
    mocker,
    mock_settings,
    mock_redis,
    mock_cache_wrapper,
    mock_vector_store,
    mock_notion_service,
    mock_chat_service,
    mock_sync_service,
    mock_audio_service,
    mock_archive_service,
):
    """Mock 全局容器"""
    container_mock = Mock()

    # 绑定所有 Fake 对象
    container_mock.config.return_value = mock_settings
    container_mock.redis_client.return_value = mock_redis
    container_mock.cache_wrapper.return_value = mock_cache_wrapper

    container_mock.vector_store.return_value = mock_vector_store
    container_mock.notion_service.return_value = mock_notion_service

    container_mock.chat_service.return_value = mock_chat_service
    container_mock.sync_service.return_value = mock_sync_service
    container_mock.audio_service.return_value = mock_audio_service
    container_mock.archive_service.return_value = mock_archive_service

    mocker.patch("core.container.container", container_mock)
    return container_mock


@pytest.fixture
def test_client(
    mock_settings,
    mock_notion_service,
    mock_vector_store,
    mock_redis,
    mock_cache_wrapper,
    mock_chat_service,
    mock_sync_service,
    mock_audio_service,
    mock_archive_service,
) -> Generator[TestClient, None, None]:
    # 覆盖依赖
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_notion_service] = lambda: mock_notion_service
    app.dependency_overrides[get_vector_store] = lambda: mock_vector_store
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_cache_wrapper] = lambda: mock_cache_wrapper

    app.dependency_overrides[get_chat_service] = lambda: mock_chat_service
    app.dependency_overrides[get_sync_service] = lambda: mock_sync_service
    app.dependency_overrides[get_audio_service] = lambda: mock_audio_service
    app.dependency_overrides[get_archive_service] = lambda: mock_archive_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def client(test_client):
    return test_client


@pytest.fixture
def auth_headers(mock_settings) -> dict:
    return {"Authorization": f"Bearer {mock_settings.API_SECRET}"}
