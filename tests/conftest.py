"""
tests/conftest.py
Global test fixtures for Exocortex test suite.
适配 v3.4+ 架构：修正导入路径，适配 DI 容器
"""

import os
import tempfile
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# 1. 设置测试环境变量 (在导入 app 之前)
os.environ["ENVIRONMENT"] = "testing"
os.environ["API_SECRET"] = "test-secret-key-must-be-long-enough-32chars"  # 需满足长度要求
os.environ["NOTION_TOKEN"] = "mock-notion-token"
os.environ["SILICON_KEY"] = "mock-silicon-key"
os.environ["DB_SPANISH_ID"] = "mock-spanish-db"


# 2. 导入应用和新的依赖路径
# 🔥 关键修正：从 api.dependencies 导入依赖函数
from api.dependencies import (  # noqa: E402
    get_cache_wrapper,
    get_notion_service,
    get_redis,
    get_settings,
    get_vector_store,
)
from config.settings import Settings  # noqa: E402
from server import app  # noqa: E402

# 尝试导入用户自定义的 Mocks，如果不存在则使用 MagicMock 兜底
try:
    from tests.mocks import MockChatModel, MockNotionService, MockVectorStore
except ImportError:
    # 定义兜底 Mock 类，防止因缺少文件导致测试无法运行
    class MockNotionService(MagicMock):
        def reset(self):
            pass

    class MockVectorStore(MagicMock):
        def reset(self):
            pass

    class MockChatModel(MagicMock):
        def reset(self):
            pass

        def __init__(self, responses=None, tool_calls=None):
            super().__init__()


# =============================================================================
# Configuration Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def mock_settings() -> Settings:
    """
    提供符合 Pydantic 结构的测试配置
    """
    # RedisClient 已经全局 mock，此处无需临时设置 Redis 相关的环境变量
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
        # Pydantic 会自动处理 PROJECT_ROOT，无需手动指定
    )


# =============================================================================
# Mock Service Fixtures
# =============================================================================


@pytest.fixture
def mock_notion_service() -> MagicMock:
    """Provide mock Notion service."""
    # 如果你有真实的 MockNotionService 类，这里会使用它
    # 否则使用 MagicMock
    service = MockNotionService()
    # 确保 mock 对象有必要的方法签名
    if isinstance(service, MagicMock):
        service.create_page.return_value = {"id": "mock-page-id"}
        service.fetch_database_content.return_value = []

    yield service
    if hasattr(service, "reset"):
        service.reset()


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Provide mock vector store."""
    store = MockVectorStore()
    if isinstance(store, MagicMock):
        store.add_memory.return_value = True
        store.search_memory.return_value = {"match": False}

    yield store
    if hasattr(store, "reset"):
        store.reset()


@pytest.fixture(autouse=True)  # <-- Add autouse=True to apply this patch automatically
def mock_redis_client_class():
    """Patch the RedisClient class to prevent actual connections during tests."""
    with (
        patch(
            "infrastructure.cache.redis_client.RedisClient", autospec=True
        ) as mock_class,
        patch("core.container.RedisClient", new=mock_class),
    ):
        # Ensure get_instance returns a mock instance
        mock_instance = MagicMock()
        mock_instance.ping.return_value = True
        mock_instance.get.return_value = None
        mock_instance.setex.return_value = True
        mock_instance.exists.return_value = False
        mock_class.get_instance.return_value = mock_instance
        yield mock_class


@pytest.fixture
def mock_redis(mock_redis_client_class) -> MagicMock:
    """Provide the *instance* of the mocked Redis client."""
    return mock_redis_client_class.get_instance()


@pytest.fixture
def mock_cache_wrapper(mock_redis) -> MagicMock:
    """Provide mock CacheWithFallback."""
    cache_mock = MagicMock()
    # 模拟 CacheWithFallback 的行为
    cache_mock.get.side_effect = mock_redis.get
    cache_mock.setex.side_effect = mock_redis.setex
    cache_mock.exists.side_effect = mock_redis.exists
    return cache_mock


# =============================================================================
# Test Client Fixtures (Core Logic)
# =============================================================================


@pytest.fixture
def test_client(
    mock_settings: Settings,
    mock_notion_service,
    mock_vector_store,
    mock_redis,
    mock_cache_wrapper,
) -> Generator[TestClient, None, None]:
    """
    Provide FastAPI test client with mocked dependencies.
    """
    # 🔥 核心修正：覆盖 api.dependencies 中的函数
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_notion_service] = lambda: mock_notion_service
    app.dependency_overrides[get_vector_store] = lambda: mock_vector_store
    app.dependency_overrides[get_redis] = lambda: mock_redis
    app.dependency_overrides[get_cache_wrapper] = lambda: mock_cache_wrapper

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def test_client_no_auth(mock_settings) -> Generator[TestClient, None, None]:
    """Provide test client without authentication mocking."""
    app.dependency_overrides[get_settings] = lambda: mock_settings

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def auth_headers(mock_settings) -> dict:
    """Provide valid authentication headers."""
    return {"Authorization": f"Bearer {mock_settings.API_SECRET}"}


@pytest.fixture
def invalid_auth_headers() -> dict:
    """Provide invalid authentication headers."""
    return {"Authorization": "Bearer invalid-token"}


@pytest.fixture
def sample_text() -> str:
    return "This is a sample document for testing purposes."


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Provide minimal PDF bytes for testing."""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 712 Td\n(Test PDF Content)\nTj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000117 00000 n\n0000000216 00000 n\ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n312\n%%EOF"


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


# 兼容旧代码的 Marker 配置
def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "api: API endpoint tests")


# tests/conftest.py (添加到现有内容)
# === Infrastructure Fixtures ===


@pytest.fixture
def redis_client():
    """提供 Redis 客户端实例"""
    from infrastructure.cache.redis_client import RedisClient

    RedisClient.reset()

    with patch("redis.ConnectionPool"):
        with patch("redis.Redis") as MockRedis:
            mock_redis_instance = MagicMock()
            mock_redis_instance.ping.return_value = True
            MockRedis.return_value = mock_redis_instance

            client = RedisClient.get_instance()
            yield client

    RedisClient.reset()


@pytest.fixture
def memory_redis():
    """提供内存 Redis 实例"""
    from infrastructure.cache.redis_client import InMemoryRedis

    redis = InMemoryRedis()
    yield redis
    redis.close()


@pytest.fixture
def cache_wrapper():
    """提供 CacheWrapper 实例"""
    from utils.cache_fallback import CacheWrapper

    with patch("infrastructure.cache.redis_client.RedisClient.get_instance"):
        cache = CacheWrapper()
        yield cache


# === Service Fixtures ===


@pytest.fixture
def mock_container():
    """提供 Mock 的依赖注入容器"""
    with patch("core.container.container") as mock:
        mock.notion_service.return_value = MagicMock()
        mock.vector_store.return_value = MagicMock()
        mock.cache.return_value = MagicMock()
        mock.audio_service.return_value = MagicMock()

        yield mock
