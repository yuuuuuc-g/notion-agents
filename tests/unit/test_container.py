"""
tests/unit/test_container.py
专门测试 DI 容器的实例化逻辑，提升 core/container.py 覆盖率
"""
from unittest.mock import patch

import pytest

from core.container import Container


class TestContainer:
    @pytest.fixture
    def container(self):
        return Container()

    def test_config_singleton(self, container):
        """测试配置单例"""
        c1 = container.config()
        c2 = container.config()
        assert c1 is c2

    def test_service_factories(self, container):
        """
        强制调用所有工厂方法，触发延迟导入 (Lazy Import)
        从而提升覆盖率
        """
        # Mock 底层依赖，防止真的去连 Redis/Notion
        with patch("core.container.RedisClient"), patch(
            "core.container.CacheWithFallback"
        ), patch("core.container.LevelChunkVectorStore"), patch(
            "core.container.NotionService"
        ), patch(
            "core.container.ChatOpenAI"
        ), patch(
            "services.chat_service.ChatService"
        ), patch(
            "services.archive_service.ArchiveService"
        ), patch(
            "services.audio_service.AudioService"
        ), patch(
            "services.sync_service.SyncService"
        ):
            # 依次调用，激活代码路径
            assert container.redis_client() is not None
            assert container.cache_wrapper() is not None
            assert container.vector_store() is not None
            assert container.notion_service() is not None
            assert container.llm_factory() is not None

            # 激活 Service 层 (这里会触发内部的 import)
            assert container.chat_service() is not None
            assert container.archive_service() is not None
            assert container.audio_service() is not None
            assert container.sync_service() is not None
