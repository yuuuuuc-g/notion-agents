"""
services/sync_service.py
同步服务 - 处理 Notion 数据库与向量库的同步
"""
import asyncio
from typing import Dict

from notion.notion_ops import NotionService
from utils.logger import get_logger
from vector.doc_store import DOC_STORE
from vector.vector_store import LevelChunkVectorStore

logger = get_logger(__name__)


def sync_notion_database(
    db_id: str,
    notion_token: str,
    vector_store: LevelChunkVectorStore,
    domain: str = "Spanish",
) -> Dict:
    """
    手动同步 Notion 数据库到向量库

    Args:
        db_id: Notion 数据库 ID
        notion_token: Notion API Token
        vector_store: 向量存储服务
        domain: 知识领域（默认 "Spanish"）

    Returns:
        同步结果字典，包含状态和统计信息
    """
    try:
        # 获取已同步的页面 ID 集合
        synced_page_ids = DOC_STORE.get_synced_page_ids(source="notion")
        logger.info(f"📋 [Manual Sync] 已同步页面数: {len(synced_page_ids)}")

        # 创建 Notion 服务并拉取内容
        service = NotionService(notion_token, db_id)
        pages_content = service.fetch_database_content(db_id)

        if not pages_content:
            logger.warning("⚠️ Notion 数据库中未找到有效内容")
            return {
                "status": "success",
                "message": "No content found in Notion.",
                "stats": {"total": 0, "new": 0, "updated": 0, "skipped": 0},
            }

        new_count = 0
        updated_count = 0
        skipped_count = 0

        for page in pages_content:
            page_id = page["id"]
            is_new = page_id not in synced_page_ids

            # 使用增量同步：如果页面已存在，也会更新
            success = vector_store.add_memory(
                page_id=page_id,
                text=page["content"],
                title=page["title"],
                domain=domain,
                metadata={"source": "notion"},
                skip_if_exists=False,  # 允许更新已存在的页面
            )

            if success:
                DOC_STORE.mark_page_synced(page_id, source="notion")
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1
            else:
                skipped_count += 1

        # 更新同步时间
        DOC_STORE.update_last_full_sync_time()

        msg = (
            f"✅ 增量同步完成: 新增 {new_count} 条, 更新 {updated_count} 条, "
            f"跳过 {skipped_count} 条, 总计 {len(pages_content)} 条。"
        )
        logger.info(f"📊 [Manual Sync] {msg}")
        return {
            "status": "success",
            "message": msg,
            "stats": {
                "total": len(pages_content),
                "new": new_count,
                "updated": updated_count,
                "skipped": skipped_count,
            },
        }

    except Exception as e:
        import traceback

        logger.error(f"❌ 同步失败: {e}\n{traceback.format_exc()}")
        return {"status": "error", "message": str(e)}


async def auto_sync_scheduler(
    db_id: str,
    notion_token: str,
    get_vector_store_func,
    get_config_func,
):
    """
    自动增量同步调度器

    Args:
        db_id: Notion 数据库 ID
        notion_token: Notion API Token
        get_vector_store_func: 获取向量存储的函数
        get_config_func: 获取配置的函数
    """
    await asyncio.sleep(30)  # 启动后等待 30 秒
    while True:
        try:
            logger.info("⏰ [Scheduler] 开始增量同步西语数据库...")
            vs = get_vector_store_func()

            # 获取已同步的页面 ID 集合（用于增量同步）
            synced_page_ids = DOC_STORE.get_synced_page_ids(source="notion")
            logger.info(f"   📋 已同步页面数: {len(synced_page_ids)}")

            # 使用之前成功的 NotionService 逻辑
            service = NotionService(notion_token, db_id)
            pages = service.fetch_database_content(db_id)

            if not pages:
                logger.info("   ℹ️ Notion 数据库中未找到内容")
            else:
                new_count = 0
                updated_count = 0
                skipped_count = 0

                for page in pages:
                    page_id = page["id"]
                    is_new = page_id not in synced_page_ids

                    # 🚀 限流保护：每篇笔记写入前等待 1.5 秒，防止触发 RPM 限制
                    await asyncio.sleep(1.5)

                    # 🔍 增量同步：新页面使用 skip_if_exists=False，已存在页面也更新
                    success = vs.add_memory(
                        page_id=page_id,
                        text=page["content"],
                        title=page["title"],
                        domain="Spanish",
                        metadata={"source": "notion"},
                        skip_if_exists=False,  # 设为 False 以支持内容更新
                    )

                    if success:
                        # 标记为已同步
                        DOC_STORE.mark_page_synced(page_id, source="notion")
                        if is_new:
                            new_count += 1
                            logger.info(f"   ✨ 新页面已同步: {page['title']}")
                        else:
                            updated_count += 1
                            logger.info(f"   🔄 页面已更新: {page['title']}")
                    else:
                        skipped_count += 1
                        logger.warning(f"   ⏭️ 跳过页面: {page['title']} (可能为空或无效)")

                # 更新最后一次全量同步时间
                DOC_STORE.update_last_full_sync_time()

                logger.info(
                    f"✅ [Scheduler] 增量同步完成: "
                    f"新增 {new_count} 条, 更新 {updated_count} 条, 跳过 {skipped_count} 条, "
                    f"总计 {len(pages)} 条内容。"
                )

            await asyncio.sleep(86400)  # 24 小时后再次同步
        except Exception as e:
            logger.error(f"⚠️ [Scheduler] 出错: {e}")
            import traceback

            logger.error(traceback.format_exc())
            await asyncio.sleep(300)  # 出错后 5 分钟重试
