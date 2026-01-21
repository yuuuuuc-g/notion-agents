"""
services/archive_service.py
归档业务服务层
"""
from notion.block_builder import markdown_to_blocks
from notion.notion_ops import NotionService
from utils.cache_fallback import CacheWithFallback
from utils.logger import get_logger
from vector.vector_store import LevelChunkVectorStore

logger = get_logger(__name__)


class ArchiveService:
    def __init__(
        self,
        redis_cache: CacheWithFallback,
        vector_store: LevelChunkVectorStore,
        notion_service: NotionService,
    ):
        self.cache = redis_cache
        self.vector_store = vector_store
        self.notion_service = notion_service

    async def archive_session(
        self, file_id: str, summary: str, thread_id: str, cleanup: bool = False
    ):
        logger.info(f"⏳ [Archive] Processing {file_id}...")

        full_text = self.cache.get(file_id)
        if not full_text:
            raise ValueError(f"File {file_id} not found in cache")

        try:
            content_blocks = markdown_to_blocks(full_text)
            page_title = f"Archive: {summary[:30]}..."

            response = self.notion_service.create_page(
                title=page_title, children=content_blocks, icon="🗃️"
            )
            notion_id = response.get("id")
            notion_url = (
                f"https://notion.so/{notion_id.replace('-', '')}" if notion_id else ""
            )

            success = self.vector_store.add_memory(
                page_id=notion_id,
                text=full_text,
                title=page_title,
                domain="General",
                metadata={"summary": summary, "thread_id": thread_id},
            )

            if cleanup:
                self.cache.delete(file_id)

            return {
                "status": "success",
                "notion_id": notion_id,
                "notion_url": notion_url,
                "vector_synced": success,
            }

        except Exception as e:
            logger.exception(f"❌ [Archive] Failed: {e}")
            raise e
