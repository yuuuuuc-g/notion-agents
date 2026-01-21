"""
services/sync_service.py
同步服务 - 处理 Notion 数据库与向量库的同步
重构版 v4.1: 修复计数逻辑 Bug
"""
import asyncio
import logging
import random
from typing import Any, Dict, Set

from notion.notion_ops import NotionService
from vector.doc_store import DOC_STORE
from vector.vector_store import LevelChunkVectorStore

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(
        self, notion_service: NotionService, vector_store: LevelChunkVectorStore
    ):
        self.notion = notion_service
        self.vector_store = vector_store
        self.semaphore = asyncio.Semaphore(3)

    async def _process_single_page(
        self, page: Dict[str, Any], synced_ids: Set[str], domain: str
    ) -> str:
        page_id = page["id"]
        title = page.get("title", "Untitled")
        is_new = page_id not in synced_ids

        for attempt in range(3):
            try:
                success = self.vector_store.add_memory(
                    page_id=page_id,
                    text=page["content"],
                    title=title,
                    domain=domain,
                    metadata={"source": "notion"},
                    skip_if_exists=False,
                )

                if success:
                    DOC_STORE.mark_page_synced(page_id, source="notion")
                    return "new" if is_new else "updated"
                return "skipped"

            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                else:
                    logger.error(f"   ❌ 同步失败 {title}: {e}")
                    return "failed"
        return "failed"

    async def sync_database(
        self,
        db_id: str,
        incremental: bool = False,
        filter: dict = None,
        retry_on_rate_limit: bool = False,
        continue_on_error: bool = False,
    ) -> Dict[str, Any]:
        """执行一次完整的数据库同步"""
        logger.info(f"🔄 [Sync] Starting sync for DB: {db_id}")

        try:
            synced_ids = DOC_STORE.get_synced_page_ids(source="notion")
            pages = await asyncio.to_thread(self.notion.fetch_database_content, db_id)

            if not pages:
                return {
                    "status": "success",
                    "synced_count": 0,
                    "message": "No pages found",
                }

            stats = {"new": 0, "updated": 0, "failed": 0, "skipped": 0}

            async def bounded_process(page):
                async with self.semaphore:
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    return await self._process_single_page(page, synced_ids, "Spanish")

            tasks = [bounded_process(page) for page in pages]
            results = await asyncio.gather(*tasks)

            for res in results:
                # ✅ 修复点：只统计一次
                stats[res] = stats.get(res, 0) + 1

            DOC_STORE.update_last_full_sync_time()

            return {
                "status": "success",
                "synced_count": stats["new"] + stats["updated"],
                "failed_count": stats["failed"],
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"❌ Sync Error: {e}")
            raise e


# 兼容旧调用的辅助函数
async def auto_sync_scheduler(
    db_id: str, notion_token: str, get_vector_store_func, get_config_func
):
    from core.container import container

    service = container.sync_service()
    await asyncio.sleep(5)
    while True:
        try:
            await service.sync_database(db_id)
            await asyncio.sleep(7200)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(300)


def sync_notion_database(db_id: str, **kwargs):
    raise NotImplementedError("Use SyncService.sync_database instead")
