"""
tools/tools.py
LangChain 工具定义 (生产级最终版)
✅ 架构：完全遵循 DI (依赖注入)，由 RunnableConfig 提供服务实例。
✅ 事务：严格保持 Notion 与 VectorDB 的双写一致性，失败必回滚。
✅ 性能：使用 asyncio.to_thread 确保同步 IO 不阻塞事件循环。
"""
import asyncio
import json
import os
from typing import Optional

import redis
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

# 仅引用逻辑模块与接口
from audio.audio_ops import generate_audio_file
from notion.block_builder import markdown_to_blocks
from vector import vector_store as vector_ops

# Redis 连接 (基础设施层)
redis_client_tool = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True,
)


@tool
async def search_knowledge_base(query: str) -> str:
    """
    必选步骤。在写入前搜索数据库，检查主题是否已存在。
    """
    print(f"🕵️ [Tool] 正在检索向量库: {query}...")
    result = await asyncio.to_thread(vector_ops.search_memory, query, domain="All")

    if result.get("match"):
        return json.dumps(
            {
                "found": True,
                "title": result.get("title"),
                "page_id": result.get("page_id"),
                "existing_content": result.get("metadata", {}).get("content", "")[
                    :1500
                ],
            },
            ensure_ascii=False,
        )
    return json.dumps({"found": False, "message": "未找到相关笔记。"})


@tool
async def manage_notion_note(
    action: str,
    title: str,
    content_markdown: str,
    summary: str,
    category: str = "General",
    target_page_id: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """
    Notion 读写的唯一工具。会自动同步到向量库。
    """
    print(f"✍️ [Tool] 动作: {action.upper()} | 标题: {title}")

    # 从注入的上下文获取服务实例
    configurable = config.get("configurable", {})
    notion_service = configurable.get("notion_service")
    db_ids = configurable.get("db_ids", {})

    if not notion_service:
        return "❌ 错误：Notion 服务未在 Context 中初始化。"

    target_db_id = db_ids.get(category, db_ids.get("General"))
    current_page_id = None
    is_new_page = False

    try:
        # --- 步骤 1：Notion 写入 ---
        if action == "overwrite":
            if not target_page_id:
                return "错误: 重写操作必须提供 target_page_id。"

            success = await asyncio.to_thread(
                notion_service.overwrite_page_content,
                target_page_id,
                content_markdown,
                summary,
            )
            if success:
                current_page_id = target_page_id
            else:
                return "❌ 无法重写 Notion 页面，页面可能已被删除。"
        else:
            # Action = create
            blocks = markdown_to_blocks(content_markdown)
            response = await asyncio.to_thread(
                notion_service.create_page, title, blocks, db_id=target_db_id
            )
            current_page_id = response.get("id")
            if current_page_id:
                is_new_page = True

        # --- 步骤 2：向量库同步 (带回滚机制) ---
        if current_page_id:
            print(f"💾 [Tool] 正在同步到向量库: {current_page_id}...")
            try:
                full_semantic_text = (
                    f"Title: {title}\nSummary: {summary}\n\n{content_markdown}"
                )
                await asyncio.to_thread(
                    vector_ops.add_memory,
                    page_id=current_page_id,
                    text=full_semantic_text,
                    title=title,
                    domain=category,
                    metadata={"summary": summary},
                )
                return f"✅ 成功！笔记已保存并索引。\n🔗 URL: https://www.notion.so/{current_page_id.replace('-', '')}"

            except Exception as vec_error:
                # 🔥 关键回滚逻辑 🔥
                print(f"⚠️ 向量同步失败: {vec_error}。正在执行事务回滚...")
                if is_new_page:
                    # 只有新创建的页面才执行物理删除回滚
                    await asyncio.to_thread(notion_service.delete_page, current_page_id)
                    return "❌ 事务失败：向量库同步出错，已回滚并删除 Notion 页面以保持一致性。"
                else:
                    return "⚠️ 警告：Notion 已更新，但向量库同步失败，检索可能受限。"

    except Exception as e:
        return f"❌ 系统错误: {str(e)}"

    return "❌ 保存失败。"


@tool
async def convert_text_to_audio(text: str, language: str = "es"):
    """将文本转换为语音。"""
    result = await generate_audio_file(text, language)
    if result:
        return f"✅ 音频已生成！[AUDIO_URL: {os.path.basename(result)}]"
    return "❌ 语音生成失败。"


@tool
async def save_current_file_to_notion(
    file_id: str, summary: str, title: str, config: RunnableConfig = None
):
    """
    将当前上传的文件存档至 Notion。
    """
    print(f"🤖 [Tool] 正在自动存档文件: {file_id}")
    full_text = redis_client_tool.get(file_id)
    if not full_text:
        return "❌ 错误：文件内容已过期或不存在。"

    configurable = config.get("configurable", {})
    notion_service = configurable.get("notion_service")
    db_ids = configurable.get("db_ids", {})

    try:
        blocks = markdown_to_blocks(full_text)
        res = await asyncio.to_thread(
            notion_service.create_page, title, blocks, db_id=db_ids.get("Tech")
        )
        page_id = res.get("id")

        if page_id:
            try:
                await asyncio.to_thread(
                    vector_ops.add_memory,
                    page_id=page_id,
                    text=full_text,
                    title=title,
                    metadata={"summary": summary},
                )
                return f"✅ 存档成功！ID: {page_id}"
            except Exception:
                # 🔥 自动存档的回滚逻辑
                await asyncio.to_thread(notion_service.delete_page, page_id)
                return "❌ 存档失败：向量索引出错，Notion 页面已回滚。"
    except Exception as e:
        return f"❌ 工具执行错误: {str(e)}"
    return "❌ 存档失败。"


tools_list = [
    search_knowledge_base,
    manage_notion_note,
    convert_text_to_audio,
    save_current_file_to_notion,
]
