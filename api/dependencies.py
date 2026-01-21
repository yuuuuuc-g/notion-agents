"""
api/dependencies.py
FastAPI 依赖注入辅助函数
包含所有服务的获取方法
"""
import redis

from core.container import container
from middleware.bandwidth_limiter import BandwidthLimiter
from notion.notion_ops import NotionService
from services.archive_service import ArchiveService
from services.audio_service import AudioService
from services.chat_service import ChatService
from services.sync_service import SyncService
from utils.cache_fallback import CacheWithFallback
from vector.vector_store import LevelChunkVectorStore

_bandwidth_limiter = BandwidthLimiter(max_mb_per_minute=100)


def get_settings():
    return container.config()


def get_redis() -> redis.Redis:
    return container.redis_client()


def get_cache_wrapper() -> CacheWithFallback:
    return container.cache_wrapper()


def get_vector_store() -> LevelChunkVectorStore:
    return container.vector_store()


def get_notion_service() -> NotionService:
    return container.notion_service()


def get_chat_service() -> ChatService:
    return container.chat_service()


def get_archive_service() -> ArchiveService:
    return container.archive_service()


def get_sync_service() -> SyncService:
    return container.sync_service()


# 🔥 补回丢失的音频服务依赖
def get_audio_service() -> AudioService:
    return container.audio_service()


def get_bandwidth_limiter() -> BandwidthLimiter:
    return _bandwidth_limiter
