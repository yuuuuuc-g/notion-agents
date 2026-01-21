"""
core/container.py
轻量级依赖注入容器 (Pure Python Version)
重构版本 v4.0.1 - 包含所有服务 (Chat, Archive, Audio, Sync)
"""
from langchain_openai import ChatOpenAI

from config.settings import SETTINGS
from infrastructure.cache.redis_client import RedisClient
from notion.notion_ops import NotionService
from utils.cache_fallback import CacheWithFallback
from vector.vector_store import LevelChunkVectorStore

# 延迟导入以避免循环依赖
# from services.chat_service import ChatService
# from services.archive_service import ArchiveService
# from services.audio_service import AudioService
# from services.sync_service import SyncService


class Container:
    """
    全局应用容器 (纯 Python 实现)
    """

    # 1. 配置
    def config(self):
        return SETTINGS

    # 2. Redis 客户端
    def redis_client(self):
        return RedisClient.get_instance()

    # 3. 缓存降级包装器
    def cache_wrapper(self):
        return CacheWithFallback(self.redis_client())

    # 4. 向量存储服务
    def vector_store(self):
        return LevelChunkVectorStore()

    # 5. Notion 服务
    def notion_service(self):
        cfg = self.config()
        return NotionService(token=cfg.NOTION_TOKEN, default_db_id=cfg.DB_SPANISH_ID)

    # 6. LLM 模型工厂
    def llm_factory(self, model: str = None):
        cfg = self.config()
        return ChatOpenAI(
            model=model or cfg.LLM_MODEL_NAME,
            openai_api_key=cfg.SILICON_KEY,
            openai_api_base=cfg.SILICON_BASE_URL,
            streaming=True,
            timeout=120,
            max_retries=2,
        )

    # 7. 聊天服务
    def chat_service(self):
        from services.chat_service import ChatService

        return ChatService(
            config=self.config(),
            notion_service=self.notion_service(),
            llm_factory=self.llm_factory,
            cache=self.cache_wrapper(),
        )

    # 8. 归档服务
    def archive_service(self):
        from services.archive_service import ArchiveService

        return ArchiveService(
            redis_cache=self.cache_wrapper(),
            vector_store=self.vector_store(),
            notion_service=self.notion_service(),
        )

    # 9. 🔥 音频服务 (补回丢失的方法)
    def audio_service(self):
        from services.audio_service import AudioService

        return AudioService(config=self.config())

    # 10. 同步服务
    def sync_service(self):
        from services.sync_service import SyncService

        return SyncService(
            notion_service=self.notion_service(), vector_store=self.vector_store()
        )


# 实例化全局容器
container = Container()
