import json
from langchain_core.tools import tool
from typing import Optional, List
import vector_ops
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
            # 截取一部分内容给 LLM 参考，避免 Token 爆炸
            "existing_content": result.get("metadata", {}).get("content", "")[:1500] 
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
    It automatically syncs the new content to the Vector Database for future retrieval.
    
    Args:
        action: "create" (for new notes) OR "overwrite" (for merging/updating).
        title: The title of the note.
        content_markdown: The full content in Markdown format (Supports tables, links, bold).
        summary: A short summary (Required for metadata).
        category: "Spanish", "Tech", or "Humanities".
        target_page_id: REQUIRED if action is "overwrite". The ID of the page to update.
    """
    print(f"✍️ [Tool] Action: {action.upper()} | Title: {title}")
    
    # 1. 构造数据包
    draft_data = {
        "title": title,
        "summary": summary,
        "markdown_body": content_markdown, # 新版 ops 核心依赖这个字段
        "tags": [category, "AI-Auto"]
    }
    
    # 2. 映射数据库 ID
    # (确保 .env 里配了这些 ID，或者 notion_ops 里有默认回退)
    db_map = {
        "Spanish": notion_ops.DB_SPANISH_ID,
        "Tech": notion_ops.DB_TECH_ID,
        "Humanities": notion_ops.DB_HUMANITIES_ID
    }
    target_db_id = db_map.get(category, notion_ops.DB_HUMANITIES_ID)

    # 3. 执行 Notion 操作
    current_page_id = None
    success = False

    if action == "overwrite":
        if not target_page_id:
            return "Error: target_page_id is required for overwrite action."
        success = notion_ops.overwrite_page_content(target_page_id, draft_data)
        if success:
            current_page_id = target_page_id
        else:
            # 🔥 关键修复：告诉 Agent 这个 ID 坏了，别再试了！
            return (
                f"❌ Critical Error: Failed to overwrite page {target_page_id}. "
                "The page might have been deleted in Notion manually. "
                "STOP retrying with this ID. "
                "Please execute `manage_notion_note` again with action='create' to generate a NEW page."
            )
            
    else:
        # Action = create
        current_page_id = notion_ops.create_general_note(draft_data, target_db_id)
        if current_page_id:
            success = True

    # 4. 🔥 关键同步：写入向量库 (Vector Sync)
    if success and current_page_id:
        print(f"💾 [Tool] Syncing to Vector DB: {current_page_id}...")
        try:
            # 构造完整的语义文本用于索引：标题 + 摘要 + 正文
            full_semantic_text = f"Title: {title}\nSummary: {summary}\n\n{content_markdown}"
            
            vector_ops.add_memory(
                page_id=current_page_id,
                text=full_semantic_text, # 使用完整 Markdown 进行索引
                title=title,
                domain=category,
                metadata={
                    "summary": summary,
                    "type": "note",
                    "content": content_markdown[:2000] # 存入 metadata 供检索时预览
                }
            )
            return f"✅ Success! Note saved to Notion and indexed in Vector DB.\n🔗 URL: https://www.notion.so/{current_page_id.replace('-', '')}"
        except Exception as e:
            return f"⚠️ Note saved to Notion, but Vector Sync failed: {e}"
            
    return "❌ Failed to save note to Notion."

# 导出工具列表
tools_list = [search_knowledge_base, manage_notion_note]