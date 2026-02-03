"""
services/sync_service.py
同步服务 v4.2
修复:
  - BUG: stats 中 failed 双重计数（+1 后又 +1）
  - BUG: domain 硬编码为 "Spanish"，改为通过参数传入
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
        self.semaphore = asyncio.Semaphore(3)  # 限流，避免触发 Notion API 速率限制

    async def _process_single_page(
        self, page: Dict[str, Any], synced_ids: Set[str], domain: str
    ) -> str:
        """处理单个页面的同步（带指数退避重试）"""
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
                    wait_time = 2 * (attempt + 1)
                    logger.warning(f"⚠️ 同步重试 [{attempt+1}/3] {title}: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ 同步失败 {title}: {e}")
                    return "failed"

        return "failed"  # 理论上不会到达，但保留以满足类型检查

    async def sync_database(
        self,
        db_id: str,
        domain: str = "General",  # 🔥 新增：domain 参数，替代硬编码
        incremental: bool = False,  # 预留参数，暂未实现
        filter: dict = None,  # 预留参数，暂未实现
    ) -> Dict[str, Any]:
        """执行一次完整的数据库同步"""
        logger.info(f"🔄 [Sync] Starting sync for DB: {db_id} (domain: {domain})")

        try:
            # 1. 已同步状态
            synced_ids = DOC_STORE.get_synced_page_ids(source="notion")

            # 2. 拉取 Notion 数据
            pages = await asyncio.to_thread(self.notion.fetch_database_content, db_id)

            if not pages:
                return {
                    "status": "success",
                    "synced_count": 0,
                    "message": "No pages found",
                }

            stats = {"new": 0, "updated": 0, "failed": 0, "skipped": 0}

            # 3. 并发处理（带随机抖动）
            async def bounded_process(page):
                async with self.semaphore:
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    return await self._process_single_page(page, synced_ids, domain)

            tasks = [bounded_process(page) for page in pages]
            results = await asyncio.gather(*tasks)

            # 4. 统计结果
            # 🔥 修复：原代码 failed 会双重 +1
            # 原代码:
            #     stats[res] = stats.get(res, 0) + 1   ← 先 +1
            #     if res == "failed":
            #         stats["failed"] += 1             ← 又 +1，bug！
            # 修复后：一行搞定
            for res in results:
                stats[res] = stats.get(res, 0) + 1

            DOC_STORE.update_last_full_sync_time()

            logger.info(f"✅ [Sync] 完成: {stats}")

            return {
                "status": "success",
                "synced_count": stats["new"] + stats["updated"],
                "failed_count": stats["failed"],
                "stats": stats,
            }

        except Exception as e:
            logger.error(f"❌ Sync Error: {e}")
            raise e


# ==========================================
# 后台自动同步调度器
# ==========================================
# 🔥 DB_ID → domain 映射表
# 如果你有多个 database，在这里添加映射
# key = db_id 的后几位或者别名，value = domain
DB_DOMAIN_MAP: Dict[str, str] = {
    "2c535e6b0ea580ce8170d8c0bebff29a": "Spanish",
    "27b35e6b0ea58030b73bc8cba55ef62d": "Tech",
    "2cd35e6b0ea580b495a0e2b0504feca7": "Humanities",
}


def resolve_domain(db_id: str) -> str:
    """从 db_id 解析 domain，找不到默认 General"""
    # 先尝试精确匹配
    if db_id in DB_DOMAIN_MAP:
        return DB_DOMAIN_MAP[db_id]
    # 再尝试 suffix 匹配（db_id 可能带 / 不带 -）
    clean_id = db_id.replace("-", "")
    for key, domain in DB_DOMAIN_MAP.items():
        if clean_id.endswith(key.replace("-", "")):
            return domain
    return "General"


async def auto_sync_scheduler(db_id: str):
    """
    后台自动同步调度器

    Args:
        db_id: 需要同步的 Notion Database ID
    """
    from core.container import container  # 函数内导入，避免循环依赖

    domain = resolve_domain(db_id)
    logger.info(f"⏰ [Scheduler] Auto-sync started for DB: {db_id} (domain: {domain})")

    service = container.sync_service()

    await asyncio.sleep(5)  # 初始延迟，等待服务器启动

    while True:
        try:
            await service.sync_database(db_id, domain=domain)
            await asyncio.sleep(7200)  # 2 小时
        except asyncio.CancelledError:
            logger.info("🛑 [Scheduler] Sync task cancelled")
            break
        except Exception as e:
            logger.error(f"⚠️ [Scheduler] Error in sync loop: {e}")
            await asyncio.sleep(300)  # 出错后 5 分钟重试
