"""
notion/notion_ops.py
只负责调用 Notion API (CRUD)
已修复: P1 级性能瓶颈 - 使用线程池并发删除 Block
已新增: delete_page 用于事务回滚
已适配: Exocortex Server V2.1 接口
"""

import concurrent.futures
from notion_client import Client
from typing import List, Dict, Any, Optional
from config.settings import SETTINGS

# 引用排版工
from .block_builder import markdown_to_blocks, parse_rich_text, _safe_str
from utils.logger import get_logger

logger = get_logger(__name__)

# === 配置 ===
# 确保 SETTINGS 里有这些字段，否则会报错
notion = Client(auth=SETTINGS.NOTION_TOKEN)

DB_SPANISH_ID = SETTINGS.DB_SPANISH_ID
DB_HUMANITIES_ID = getattr(SETTINGS, "DB_HUMANITIES_ID", None)  # 防御性获取
DB_TECH_ID = getattr(SETTINGS, "DB_TECH_ID", None)  # 防御性获取

# 默认使用的数据库 (如果调用时不指定，就存这里)
DEFAULT_DB_ID = DB_TECH_ID if DB_TECH_ID else DB_SPANISH_ID


def _append_children_in_batches(page_id: str, children: List[Dict]):
    """分批追加 Block，防止超过 100 个限制"""
    if not children:
        return
    batch_size = 100
    batches = [
        children[i : i + batch_size] for i in range(0, len(children), batch_size)
    ]
    logger.info(f"📡 Uploading {len(children)} blocks in {len(batches)} batches...")
    for idx, batch in enumerate(batches):
        try:
            notion.blocks.children.append(block_id=page_id, children=batch)
            logger.info(f"   - ✅ Batch {idx + 1}/{len(batches)} uploaded.")
        except Exception as e:
            logger.error(f"   - ❌ Batch {idx + 1} failed: {e}")


# 🔥🔥🔥 新增适配接口：供 Server.py 调用 🔥🔥🔥
def create_notion_page(
    title: str, children: List[Dict], icon: str = "🧠", db_id: str = None
) -> Dict:
    """
    Exocortex Server 专用接口
    直接接收已经转换好的 Blocks (children)
    """
    target_db = db_id if db_id else DEFAULT_DB_ID
    if not target_db:
        raise ValueError("❌ No Database ID configured in settings!")

    logger.info(f"✍️ [Notion Ops] Creating Page: {title}")

    # Notion 创建页面时，children 限制为 100 个
    # 我们先切分：前 100 个随页面创建，剩下的分批追加
    initial_batch = children[:100]
    remaining_blocks = children[100:]

    try:
        response = notion.pages.create(
            parent={"database_id": target_db},
            icon={"type": "emoji", "emoji": icon},
            properties={
                "Name": {"title": [{"text": {"content": title}}]},
                # "Type": {"select": {"name": "Exocortex"}} # 可选：加个标签
            },
            children=initial_batch,
        )
        page_id = response["id"]
        logger.info(f"✅ Page Created: {page_id}")

        # 如果还有剩下的，复用你写好的批量上传逻辑
        if remaining_blocks:
            _append_children_in_batches(page_id, remaining_blocks)

        return response

    except Exception as e:
        logger.error(f"❌ Create Failed: {e}")
        # 抛出异常让 Server 知道失败了，不要吞掉
        raise e


# --- 以下保留你原有的函数，供其他模块使用 ---


def create_general_note(
    data: Dict, target_db_id: str, original_url: str = None
) -> Optional[str]:
    """旧版接口：保留兼容性"""
    title = _safe_str(data.get("title", "Untitled"))
    summary = data.get("summary")
    markdown_body = data.get("markdown_body", "")

    # ... (原有逻辑保持不变，或者你可以让它直接调用 create_notion_page) ...
    # 为了保险，先保留你原来的代码不动

    children = []
    if summary:
        children.append(
            {
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": parse_rich_text(summary),
                    "icon": {"emoji": "💡"},
                    "color": "gray_background",
                },
            }
        )

    if markdown_body:
        children.extend(markdown_to_blocks(markdown_body))

    # 直接复用新接口，减少重复代码！
    try:
        res = create_notion_page(title, children, icon="📝", db_id=target_db_id)
        return res["id"]
    except Exception:
        return None


def append_to_page(page_id: str, data: Dict, restore_mode: bool = False) -> bool:
    """向现有页面追加内容 (保持不变)"""
    logger.info(f"➕ [Notion Ops] Appending to {page_id}")
    children = []
    summary = data.get("summary")
    title = _safe_str(data.get("title", "Update"))

    if restore_mode:
        if summary:
            children.append(
                {
                    "object": "block",
                    "type": "callout",
                    "callout": {
                        "rich_text": parse_rich_text(summary),
                        "icon": {"emoji": "💡"},
                        "color": "gray_background",
                    },
                }
            )
    else:
        children.extend(
            [
                {"object": "block", "type": "divider", "divider": {}},
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": f"Update: {title}"}}],
                        "color": "blue_background",
                    },
                },
            ]
        )

    if data.get("markdown_body"):
        children.extend(markdown_to_blocks(data["markdown_body"]))
    else:
        raw = str(data.get("blocks", ""))
        children.append(
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": raw}}]},
            }
        )

    try:
        _append_children_in_batches(page_id, children)
        return True
    except Exception as e:
        logger.error(f"❌ Append Failed: {e}")
        return False


def _delete_block_worker(block_id: str):
    """辅助函数：供线程池调用"""
    try:
        notion.blocks.delete(block_id=block_id)
    except Exception as e:
        logger.warning(f"   ⚠️ Delete block {block_id} failed: {e}")


def overwrite_page_content(page_id: str, draft_data: Dict) -> bool:
    """覆盖页面内容 (保持不变)"""
    logger.info(f"♻️ [Notion Ops] Overwriting page {page_id}...")
    try:
        # 1. 获取所有子 Block ID
        all_block_ids = []
        has_more = True
        start_cursor = None

        while has_more:
            response = notion.blocks.children.list(
                block_id=page_id, start_cursor=start_cursor
            )
            blocks = response.get("results", [])
            for b in blocks:
                all_block_ids.append(b["id"])
            has_more = response.get("has_more")
            start_cursor = response.get("next_cursor")

        # 2. 并发删除
        if all_block_ids:
            logger.info(f"   - Deleting {len(all_block_ids)} blocks (Parallel)...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(_delete_block_worker, all_block_ids)

        logger.info("   - 🗑️ Old content cleared.")

        # 3. 写入新内容
        return append_to_page(page_id, draft_data, restore_mode=True)

    except Exception as e:
        logger.error(f"❌ Overwrite Failed: {e}")
        return False


def delete_page(page_id: str) -> bool:
    """归档页面 (保持不变)"""
    logger.info(f"🧨 [Notion Ops] Deleting (Archiving) page {page_id}...")
    try:
        notion.pages.update(page_id=page_id, archived=True)
        return True
    except Exception as e:
        logger.error(f"❌ Delete Page Failed: {e}")
        return False


def get_page_text(page_id: str) -> str:
    # 保持不变
    logger.info(f"📖 [Notion Ops] Reading {page_id}...")
    try:
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])
        lines = []
        for b in blocks:
            b_type = b.get("type")
            if "rich_text" in b.get(b_type, {}):
                text_objs = b[b_type]["rich_text"]
                plain = "".join([t.get("plain_text", "") for t in text_objs])
                if plain:
                    lines.append(plain)
            elif b_type == "code":
                text_objs = b["code"].get("rich_text", [])
                code = "".join([t.get("plain_text", "") for t in text_objs])
                lines.append(f"```\n{code}\n```")
        return "\n\n".join(lines)
    except Exception as e:
        logger.error(f"❌ Read Failed: {e}")
        return ""
