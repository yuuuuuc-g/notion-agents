"""
core/container.py
轻量级依赖注入容器 (Pure Python Version)
重构版本 v4.1.0 - 适配 Merged VectorStore (v5)
"""

from langchain_openai import ChatOpenAI

from config.settings import SETTINGS
from infrastructure.cache.redis_client import RedisClient
from notion.notion_ops import NotionService
from utils.cache_fallback import CacheWithFallback
from vector.hybrid_search import HybridSearchEngine
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

    # 4. 向量存储服务 (Updated to use v5 Merged Store)
    def vector_store(self) -> LevelChunkVectorStore:
        """
        向量存储服务
        特性：层次化分块 + 混合检索 (Dense + Sparse Fusion)
        """
        return LevelChunkVectorStore()

    # 5. 混合检索引擎 (Hybrid Search Engine)
    def hybrid_search_engine(self) -> HybridSearchEngine:
        """
        混合检索引擎，包含向量搜索、关键词搜索和重排序功能
        """
        # 重用向量存储的 Qdrant 客户端和 Embedding 提供器
        vector_store = self.vector_store()
        # 获取 Qdrant 客户端
        qdrant_client = vector_store.client
        # 获取 Embedding 提供器
        embedding_provider = vector_store.embedding_provider
        # 创建 HybridSearchEngine 实例
        return HybridSearchEngine(
            qdrant_client=qdrant_client,
            embedding_provider=embedding_provider,
            notion_service=self.notion_service(),
            collection_name="biobrain_memory",  # 与向量存储保持一致
        )

    # 6. Notion 服务
    def notion_service(self):
        cfg = self.config()
        return NotionService(token=cfg.NOTION_TOKEN, default_db_id=cfg.DB_SPANISH_ID)

    # 6. LLM 模型工厂
    def llm_factory(self, model: str = None):
        cfg = self.config()
        return ChatOpenAI(
            model=model or cfg.LLM_MODEL_NAME,
            openai_api_key=cfg.DEEPSEEK_API_KEY,
            openai_api_base=cfg.DEEPSEEK_BASE_URL,
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

    # 9. 音频服务
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
