import json
from langchain_core.tools import tool
from typing import Optional, List
import vector_ops
from vector_ops import add_memory
import notion_ops

@tool
def search_knowledge_base(query: str) -> str:
    """
    REQUIRED step before writing.
    Search the database to check if a topic already exists.
    Useful for finding duplicate notes or answering questions.
    """
    print(f"🕵️ [Tool] Searching: {query}...")
    # 强制全库搜索
    result = vector_ops.search_memory(query, domain="All")
    
    if result.get("match"):
        return json.dumps({
            "found": True,
            "title": result.get("title"),
            "page_id": result.get("page_id"),
            "summary": result.get("metadata", {}).get("summary", ""),
            "existing_content": result.get("metadata", {}).get("content", "")[:1000] # 截取一部分给LLM参考
        }, ensure_ascii=False)
    else:
        return json.dumps({"found": False, "message": "No relevant notes found."})

@tool
def manage_notion_note(
    action: str,
    title: str,
    content_markdown: str,
    summary: str,
    category: str = "General",
    target_page_id: Optional[str] = None
) -> str:
    """
    The ONLY tool to write/save content to Notion.
    
    Args:
        action: "create" (for new notes) OR "overwrite" (for merging/updating).
        title: The title of the note.
        content_markdown: The full content in Markdown format.
        summary: A short summary (Required for metadata).
        category: "Spanish", "Tech", or "Humanities".
        target_page_id: REQUIRED if action is "overwrite". The ID of the page to update.
    """
    print(f"✍️ [Tool] Action: {action.upper()} | Title: {title}")
    
    # 构造数据包
    draft_data = {
        "title": title,
        "summary": summary,
        "markdown_body": content_markdown,
        "tags": [category, "AI-Auto"]
    }
    
    # 映射数据库ID
    db_map = {
        "Spanish": notion_ops.DB_SPANISH_ID,
        "Tech": notion_ops.DB_TECH_ID,
        "Humanities": notion_ops.DB_HUMANITIES_ID
    }
    target_db_id = db_map.get(category, notion_ops.DB_HUMANITIES_ID)

    if action == "overwrite":
        if not target_page_id:
            return "Error: target_page_id is required for overwrite action."
        success = notion_ops.overwrite_page_content(target_page_id, draft_data)
        if success:
            add_memory(
                page_id=target_page_id,
                content=content_markdown,
                title=title,
                category=category,
                metadata={
                    "summary": summary,
                    "content": content_markdown
                }
            )
            return f"Successfully merged/overwritten page {target_page_id}"
        else:
            return "Failed to overwrite."
        
    else:
        # Action = create
        page_id = notion_ops.create_general_note(draft_data, target_db_id)
        if page_id:
            add_memory(
                page_id=page_id,
                content=content_markdown,
                title=title,
                category=category,
                metadata={
                    "summary": summary,
                    "content": content_markdown
                }
            )
            return f"Successfully created new page: {page_id}"
        else:
            return "Failed to create page."

# 导出工具列表
tools_list = [search_knowledge_base, manage_notion_note]