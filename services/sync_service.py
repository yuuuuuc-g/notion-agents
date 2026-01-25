"""
services/sync_service.py
同步服务 - 处理 Notion 数据库与向量库的同步
版本：v4.1 (Cleaned)
变更：移除了未使用的 container 引用、遗留的函数参数和死代码
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
        self.semaphore = asyncio.Semaphore(3)  # 控制并发数，防止触发 Notion API 限制

    async def _process_single_page(
        self, page: Dict[str, Any], synced_ids: Set[str], domain: str
    ) -> str:
        """处理单个页面的同步与重试逻辑"""
        page_id = page["id"]
        title = page.get("title", "Untitled")
        is_new = page_id not in synced_ids

        # 简单的指数退避重试
        for attempt in range(3):
            try:
                # 尝试写入向量库 (V5 混合检索版)
                success = self.vector_store.add_memory(
                    page_id=page_id,
                    text=page["content"],
                    title=title,
                    domain=domain,
                    metadata={"source": "notion"},
                    skip_if_exists=False,  # 强制更新内容
                    # TODO: 如果 NotionOps 将来支持返回 blocks 结构，
                    # 可以在这里传入 notion_blocks=page['blocks'] 以启用更精准的层次化分块
                )

                if success:
                    DOC_STORE.mark_page_synced(page_id, source="notion")
                    return "new" if is_new else "updated"
                return "skipped"

            except Exception as e:
                if attempt < 2:
                    wait_time = 2 * (attempt + 1)
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"   ❌ 同步失败 {title}: {e}")
                    return "failed"
        return "failed"

    async def sync_database(
        self,
        db_id: str,
        incremental: bool = False,  # 预留参数，暂未使用
        filter: dict = None,  # 预留参数，暂未使用
    ) -> Dict[str, Any]:
        """执行一次完整的数据库同步"""
        logger.info(f"🔄 [Sync] Starting sync for DB: {db_id}")

        try:
            # 1. 获取已同步状态
            synced_ids = DOC_STORE.get_synced_page_ids(source="notion")

            # 2. 从 Notion 拉取数据
            pages = await asyncio.to_thread(self.notion.fetch_database_content, db_id)

            if not pages:
                return {
                    "status": "success",
                    "synced_count": 0,
                    "message": "No pages found",
                }

            stats = {"new": 0, "updated": 0, "failed": 0, "skipped": 0}

            # 3. 限制并发处理
            async def bounded_process(page):
                async with self.semaphore:
                    # 随机抖动，避免瞬间并发峰值
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    return await self._process_single_page(page, synced_ids, "Spanish")

            # 4. 执行任务
            tasks = [bounded_process(page) for page in pages]
            results = await asyncio.gather(*tasks)

            # 5. 统计结果
            for res in results:
                stats[res] = stats.get(res, 0) + 1
                if res == "failed":
                    stats["failed"] += 1

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


async def auto_sync_scheduler(db_id: str):
    """
    后台自动同步调度器

    Args:
        db_id: 需要同步的 Notion Database ID
    """
    # 在函数内部导入 container，彻底解决循环依赖问题
    from core.container import container

    logger.info(f"⏰ [Scheduler] Auto-sync started for DB: {db_id}")

    # 通过容器获取服务实例
    service = container.sync_service()

    # 初始延迟，等待服务器完全启动
    await asyncio.sleep(5)

    while True:
        try:
            await service.sync_database(db_id)
            # 每 2 小时同步一次
            await asyncio.sleep(7200)
        except asyncio.CancelledError:
            logger.info("🛑 [Scheduler] Sync task cancelled")
            break
        except Exception as e:
            logger.error(f"⚠️ [Scheduler] Error in sync loop: {e}")
            # 出错后等待 5 分钟再试
            await asyncio.sleep(300)
