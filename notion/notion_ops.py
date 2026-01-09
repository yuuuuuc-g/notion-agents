"""
notion/notion_ops.py
只负责调用 Notion API (CRUD)，依赖 block_builder 生成数据
"""
import requests
from notion_client import Client
from typing import List, Dict, Any, Optional
from config.settings import SETTINGS

# 👇 引用旁边的排版工
from .block_builder import markdown_to_blocks, parse_rich_text, _safe_str

# === 配置 ===
notion = Client(auth=SETTINGS.NOTION_TOKEN)

DB_SPANISH_ID = SETTINGS.DB_SPANISH_ID
DB_HUMANITIES_ID = SETTINGS.DB_HUMANITIES_ID
DB_TECH_ID = SETTINGS.DB_TECH_ID


def _append_children_in_batches(page_id: str, children: List[Dict]):
    if not children: return
    batch_size = 100
    batches = [children[i : i + batch_size] for i in range(0, len(children), batch_size)]
    print(f"📡 Uploading {len(children)} blocks in {len(batches)} batches...")
    for idx, batch in enumerate(batches):
        try:
            notion.blocks.children.append(block_id=page_id, children=batch)
            print(f"   - ✅ Batch {idx + 1}/{len(batches)} uploaded.")
        except Exception as e:
            print(f"   - ❌ Batch {idx + 1} failed: {e}")

# 注意：现在的 create_general_note 等函数里，调用 markdown_to_blocks 时
# 实际上是调用从 .block_builder 导入的那个函数。

def create_general_note(data: Dict, target_db_id: str, original_url: str = None) -> Optional[str]:
    title = _safe_str(data.get('title', 'Untitled'))
    summary = data.get('summary')
    markdown_body = data.get('markdown_body', '')
    
    print(f"✍️ [Notion Ops] Creating Note: {title}")
    
    children = []
    if summary:
        children.append({
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": parse_rich_text(summary),
                "icon": {"emoji": "💡"}, "color": "gray_background"
            }
        })
    
    if markdown_body:
        children.extend(markdown_to_blocks(markdown_body))
    
    try:
        initial_batch = children[:100]
        remaining_blocks = children[100:]
        
        response = notion.pages.create(
            parent={"database_id": target_db_id},
            properties={
                "Name": {"title": [{"text": {"content": title}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
                "Type": {"select": {"name": "Article"}},
                "URL": {"url": original_url if original_url else None}
            },
            children=initial_batch
        )
        page_id = response["id"]
        print(f"✅ Page Created: {page_id}")

        if remaining_blocks:
            _append_children_in_batches(page_id, remaining_blocks)
        return page_id

    except Exception as e:
        print(f"❌ Create Failed: {e}")
        return None


def append_to_page(page_id: str, data: Dict, restore_mode: bool = False) -> bool:

    print(f"➕ [Notion Ops] Appending to {page_id}")
    children = []
    summary = data.get("summary")
    title = _safe_str(data.get('title', 'Update'))

    if restore_mode:
        if summary:
            children.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": parse_rich_text(summary),
                    "icon": {"emoji": "💡"}, "color": "gray_background"
                }
            })
    else:
        children.extend([
            {"object": "block", "type": "divider", "divider": {}},
            {"object": "block", "type": "heading_2", "heading_2": {
                "rich_text": [{"text": {"content": f"Update: {title}"}}], 
                "color": "blue_background"
            }}
        ])

    if data.get("markdown_body"):
        children.extend(markdown_to_blocks(data["markdown_body"]))
    else:
        raw = str(data.get("blocks", ""))
        children.append({
            "object": "block", "type": "paragraph", 
            "paragraph": {"rich_text": [{"text": {"content": raw}}]}
        })

    try:
        _append_children_in_batches(page_id, children)
        return True
    except Exception as e:
        print(f"❌ Append Failed: {e}")
        return False

def overwrite_page_content(page_id: str, draft_data: Dict) -> bool:
    # 逻辑保持不变
    print(f"♻️ [Notion Ops] Overwriting page {page_id}...")
    try:
        has_more = True
        start_cursor = None
        while has_more:
            response = notion.blocks.children.list(block_id=page_id, start_cursor=start_cursor)
            blocks = response.get("results", [])
            for b in blocks:
                notion.blocks.delete(block_id=b["id"])
            has_more = response.get("has_more")
            start_cursor = response.get("next_cursor")
        
        print("   - 🗑️ Old content cleared.")
        return append_to_page(page_id, draft_data, restore_mode=True)
    except Exception as e:
        print(f"❌ Overwrite Failed: {e}")
        return False

def get_page_text(page_id: str) -> str:
    # 逻辑保持不变
    print(f"📖 [Notion Ops] Reading {page_id}...")
    try:
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])
        lines = []
        for b in blocks:
            b_type = b.get("type")
            if "rich_text" in b.get(b_type, {}):
                text_objs = b[b_type]["rich_text"]
                plain = "".join([t.get("plain_text", "") for t in text_objs])
                if plain: lines.append(plain)
            elif b_type == "code":
                text_objs = b["code"].get("rich_text", [])
                code = "".join([t.get("plain_text", "") for t in text_objs])
                lines.append(f"```\n{code}\n```")
        return "\n\n".join(lines)
    except Exception as e:
        print(f"❌ Read Failed: {e}")
        return ""