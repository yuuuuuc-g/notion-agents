"""
api/routes/notion.py
Notion 相关端点 - HITL 人工确认机制
"""
import asyncio
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import get_cache_wrapper
from core.container import container
from middleware.auth import verify_token
from middleware.error_handler import BusinessException
from notion.block_builder import markdown_to_blocks
from utils.cache_fallback import CacheWithFallback

router = APIRouter(tags=["Notion"])


class NotionConfirmRequest(BaseModel):
    draft_id: str
    approved: bool  # True = 批准写入, False = 拒绝


@router.post("/notion/confirm", dependencies=[Depends(verify_token)])
async def confirm_notion_write(
    body: NotionConfirmRequest,
    cache: CacheWithFallback = Depends(get_cache_wrapper),
):
    """
    确认或拒绝 Notion 写入操作（HITL 人工确认端点）

    Args:
        draft_id: 草稿 ID（从 Redis 缓存中获取）
        approved: 是否批准写入
    """
    print(f"🛡️ [HITL] 收到确认请求: draft_id={body.draft_id}, approved={body.approved}")

    # 从缓存中获取草稿
    draft_json = cache.get(body.draft_id)
    if not draft_json:
        raise BusinessException(
            message="草稿已过期或不存在（TTL 1小时）",
            code="DRAFT_EXPIRED",
            status_code=404,
        )

    # 解析草稿数据
    try:
        draft_data = json.loads(draft_json)
    except json.JSONDecodeError:
        raise BusinessException(
            message="草稿数据格式错误", code="INVALID_DRAFT", status_code=400
        )

    # 提取草稿字段
    title = draft_data.get("title")
    content_markdown = draft_data.get("content_markdown")
    summary = draft_data.get("summary")
    category = draft_data.get("category")
    target_db_id = draft_data.get("target_db_id")

    # 用户拒绝写入
    if not body.approved:
        print(f"❌ [HITL] 用户拒绝写入: {title}")
        cache.delete(body.draft_id)  # 清理缓存
        return {
            "status": "rejected",
            "message": "✅ 已取消写入操作",
        }

    # 用户批准写入 - 执行真实的 Notion 创建
    print(f"✅ [HITL] 用户批准写入: {title}")

    notion_service = container.notion_service()
    vector_store = container.vector_store()

    try:
        # 构建内容（添加摘要引用块）
        content_with_summary = f"""
> 📝 **摘要**: {summary}

---

{content_markdown}
"""

        blocks = markdown_to_blocks(content_with_summary)

        # 创建 Notion 页面
        response = await asyncio.to_thread(
            notion_service.create_page,
            title=title,
            children=blocks,
            db_id=target_db_id,
            category=category,
            tags=[category, "AI生成", "人工审核"] if category else ["AI生成", "人工审核"],
        )

        page_id = response.get("id")

        if not page_id:
            raise BusinessException(
                message="Notion 页面创建失败", code="NOTION_CREATE_FAILED", status_code=500
            )

        print(f"✅ [HITL] Notion 页面已创建: {page_id}")

        # 同步到向量库
        try:
            full_semantic_text = (
                f"Title: {title}\n"
                f"Summary: {summary}\n"
                f"Category: {category}\n\n"
                f"{content_markdown}"
            )

            await asyncio.to_thread(
                vector_store.add_memory,
                page_id=page_id,
                text=full_semantic_text,
                title=title,
                domain=category,
                metadata={
                    "summary": summary,
                    "category": category,
                    "action": "create",
                    "hitl_approved": True,
                },
            )

            print("✅ [HITL] 向量库同步成功")

            # 清理缓存
            cache.delete(body.draft_id)

            return {
                "status": "success",
                "message": "✅ 笔记已成功写入 Notion 并索引",
                "page_id": page_id,
                "url": f"https://www.notion.so/{page_id.replace('-', '')}",
            }

        except Exception as vec_error:
            # 向量同步失败 - 回滚 Notion 页面
            print(f"❌ [HITL] 向量同步失败: {vec_error}")
            print("🔄 [HITL] 正在回滚 Notion 页面...")

            try:
                await asyncio.to_thread(notion_service.delete_page, page_id)
                print("✅ [HITL] 已回滚并删除 Notion 页面")
            except Exception as rollback_error:
                print(f"❌ [HITL] 回滚失败: {rollback_error}")

            raise BusinessException(
                message=f"向量库同步失败，已回滚 Notion 页面: {str(vec_error)}",
                code="VECTOR_SYNC_FAILED",
                status_code=500,
            )

    except BusinessException:
        raise
    except Exception as e:
        print(f"❌ [HITL] Notion 创建失败: {e}")
        raise BusinessException(
            message=f"Notion 写入失败: {str(e)}",
            code="NOTION_WRITE_FAILED",
            status_code=500,
        )
