"""
services/archive_service.py
归档服务 - 处理会话归档到 Notion 和向量库
"""
import redis

from notion.block_builder import markdown_to_blocks
from utils.logger import get_logger

logger = get_logger(__name__)


def archive_session(
    file_id: str,
    summary: str,
    thread_id: str,
    redis_client: redis.Redis,
    vector_store,
    notion_service,
):
    """
    将会话归档到 Notion 和向量库

    Args:
        file_id: 会话文件 ID
        summary: 归档摘要
        thread_id: 线程 ID
        redis_client: Redis 客户端
        vector_store: 向量存储服务
        notion_service: Notion 服务
    """
    logger.info(f"⏳ [Background] Archiving session {file_id}...")
    full_text = redis_client.get(file_id)
    if not full_text:
        logger.error("❌ Context not found.")
        return

    try:
        # 1. Notion 归档
        content_blocks = markdown_to_blocks(full_text)
        page_title = f"Exocortex Archive: {summary[:50]}..."
        response = notion_service.create_page(title=page_title, children=content_blocks)
        notion_page_id = response.get("id")

        # 2. 存储到向量库
        success = vector_store.add_memory(
            page_id=notion_page_id,
            text=full_text,
            title=page_title,
            domain="General",
            metadata={"summary": summary},
        )
        if success:
            logger.info("✅ Indexed to ChromaDB using Dependency Injection!")
    except Exception:
        logger.exception("❌ Error during archiving")
