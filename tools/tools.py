"""
tools/tools.py
LangChain 工具定义
已修复: 
1. P0 同步阻塞 (asyncio.to_thread)
2. P1 双写不一致 (添加事务回滚逻辑)
"""
import json
import asyncio
from langchain_core.tools import tool
from typing import Optional
import redis
import os

# 引用各个业务模块
from audio.audio_ops import generate_audio_file
from notion import notion_ops
from vector import vector_store as vector_ops

@tool
async def search_knowledge_base(query: str) -> str:
    """
    REQUIRED step before writing.
    Search the database to check if a topic already exists.
    Useful for finding duplicate notes or answering questions.
    """
    print(f"🕵️ [Tool] Searching: {query}...")
    
    result = await asyncio.to_thread(vector_ops.search_memory, query, domain="All")
    
    if result.get("match"):
        return json.dumps({
            "found": True,
            "title": result.get("title"),
            "page_id": result.get("page_id"),
            "summary": result.get("metadata", {}).get("summary", ""),
            "existing_content": result.get("metadata", {}).get("content", "")[:1500] 
        }, ensure_ascii=False)
    else:
        return json.dumps({"found": False, "message": "No relevant notes found."})

@tool
async def manage_notion_note(
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
        action: "create" OR "overwrite".
        title: The title of the note.
        content_markdown: The full content in Markdown format.
        summary: A short summary.
        category: Must be one of ["Spanish", "Tech", "Humanities", "General"].
        target_page_id: REQUIRED if action is "overwrite".
    """
    print(f"✍️ [Tool] Action: {action.upper()} | Title: {title}")
    
    draft_data = {
        "title": title,
        "summary": summary,
        "markdown_body": content_markdown,
        "tags": [category, "AI-Auto"]
    }
    
    db_map = {
        "Spanish": notion_ops.DB_SPANISH_ID,
        "Tech": notion_ops.DB_TECH_ID,
        "Humanities": notion_ops.DB_HUMANITIES_ID
    }
    target_db_id = db_map.get(category, notion_ops.DB_HUMANITIES_ID)

    current_page_id = None
    success = False
    is_new_page = False # 标记是否是新创建的页面，用于回滚判断

    try:
        # --- 第一步：Notion 操作 ---
        if action == "overwrite":
            if not target_page_id:
                return "Error: target_page_id is required for overwrite action."
            
            success = await asyncio.to_thread(
                notion_ops.overwrite_page_content, 
                target_page_id, 
                draft_data
            )
            if success: current_page_id = target_page_id
            else:
                return "❌ Failed to overwrite Notion page. It might be deleted."
                
        else:
            # Action = create
            current_page_id = await asyncio.to_thread(
                notion_ops.create_general_note, 
                draft_data, 
                target_db_id
            )
            if current_page_id:
                success = True
                is_new_page = True

        # --- 第二步：Vector 同步 (带回滚) ---
        if success and current_page_id:
            print(f"💾 [Tool] Syncing to Vector DB: {current_page_id}...")
            
            try:
                # 尝试写入向量库
                full_semantic_text = f"Title: {title}\nSummary: {summary}\n\n{content_markdown}"
                
                await asyncio.to_thread(
                    vector_ops.add_memory,
                    page_id=current_page_id,
                    text=full_semantic_text,
                    title=title,
                    domain=category,
                    metadata={
                        "summary": summary,
                        "type": "note",
                        "content": content_markdown[:2000]
                    }
                )
                
                return f"✅ Success! Note saved to Notion and indexed in Vector DB.\n🔗 URL: https://www.notion.so/{current_page_id.replace('-', '')}"

            except Exception as vec_error:
                # 🔥 关键回滚逻辑 🔥
                print(f"⚠️ Vector Sync Failed: {vec_error}. Initiating Rollback...")
                
                # 只有当这是新创建的页面时，我们才删除它进行回滚
                # 如果是 overwrite，删除页面会导致用户旧数据丢失，所以overwrite失败一般保留页面但报错
                if is_new_page:
                    await asyncio.to_thread(notion_ops.delete_page, current_page_id)
                    return f"❌ Error: Vector database sync failed ({vec_error}). To ensure data consistency, the Notion page was NOT saved (Rolled back)."
                else:
                    return f"⚠️ Warning: Note updated in Notion, but Vector sync failed ({vec_error}). Search capability for this note may be broken."

    except Exception as e:
        return f"❌ System Error in manage_notion_note: {str(e)}"
            
    return "❌ Failed to save note to Notion."

@tool
async def convert_text_to_audio(text: str, language: str = 'es'):
    """
    Converts text to audio file. 
    Use this tool IMMEDIATELY when user asks for "speak", "read", "audio", or "listen".
    """
    result = await generate_audio_file(text, language)
    if result:
        return f"✅ Audio generated successfully. Path: {result}"
    else:
        return "❌ Audio generation failed."

redis_client_tool = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True 
)

@tool
async def save_current_file_to_notion(file_id: str, summary: str, title: str):
    """
    Use this tool ONLY when the user asks to "save", "archive", or "keep" the CURRENTLY uploaded file to Notion.
    The tool will automatically fetch the full content from Redis using the file_id.
    
    Args:
        file_id: The ID of the file (provided in the system prompt context).
        summary: A short summary of the content.
        title: A title for the Notion page.
    """
    print(f"🤖 [Tool] Agent triggering auto-save for file: {file_id}")
    
    # 1. 工具自己去 Redis 拿原文，不劳烦 AI 传参
    full_text = redis_client_tool.get(file_id)
    
    if not full_text:
        return "❌ Error: File content expired or not found. Please upload again."

    # 2. 调用你已有的逻辑 (复用 manage_notion_note 的内部逻辑，或者直接调 notion_ops)
    # 这里我们模拟调用 manage_notion_note 的行为
    try:
        draft_data = {
            "title": title,
            "summary": summary,
            "markdown_body": full_text, # 填入原文
            "tags": ["Agent-Archived"]
        }
        
        # 默认存到 Tech 库 (你可以改为让 AI 传 category)
        page_id = await asyncio.to_thread(
            notion_ops.create_general_note, 
            draft_data, 
            notion_ops.DB_TECH_ID 
        )
        
        if page_id:
            # 3. 顺便做向量化
            await asyncio.to_thread(
                vector_ops.add_memory,
                page_id=page_id,
                text=full_text,
                title=title,
                metadata={"summary": summary}
            )
            return f"✅ Successfully saved to Notion! Page ID: {page_id}"
        else:
            return "❌ Failed to create Notion page."
            
    except Exception as e:
        return f"❌ Tool Error: {str(e)}"
    
tools_list = [search_knowledge_base, manage_notion_note, convert_text_to_audio, save_current_file_to_notion]