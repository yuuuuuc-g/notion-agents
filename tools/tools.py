"""
tools/tools.py
LangChain 工具定义 (Refactored v3.3 - 防重复 + 强制分类)
修复:
1. 添加自动查重机制 (相似度 > 0.85 拒绝创建)
2. 强制分类 (移除 category 默认值)
3. 改进错误处理和事务回滚
"""
import asyncio
import json
import os
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from core.container import container
from notion.block_builder import markdown_to_blocks


@tool
async def search_knowledge_base(query: str) -> str:
    """
    轻量级搜索工具 - 用于快速查重

    主要用途:
    - 在写入新笔记前，检查是否已存在相似主题
    - 防止重复内容

    如果是回答用户复杂的知识性问题，请优先使用 conversational_search。

    Args:
        query: 搜索查询 (标题或摘要)

    Returns:
        JSON 格式的搜索结果
    """
    # 中文说明：Tool 必须永远返回可解析的 JSON，避免异常冒泡导致 LLM 只看到“工具崩了”而无法纠错
    try:
        print(f"🕵️ [Tool] 正在检索向量库 (Lite): {query}...")

        vector_store = container.vector_store()
        result = await asyncio.to_thread(
            vector_store.search_memory, query, domain="All"
        )

        if result.get("match"):
            return json.dumps(
                {
                    "found": True,
                    "title": result.get("title"),
                    "page_id": result.get("page_id"),
                    "score": result.get("distance", 0.0),
                    "domain": result.get("domain", "General"),
                    "existing_content": result.get("metadata", {}).get("content", "")[
                        :1500
                    ],
                },
                ensure_ascii=False,
            )
        return json.dumps({"found": False, "message": "未找到相关笔记。"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps(
            {"found": False, "error": f"轻量检索失败: {str(e)}"},
            ensure_ascii=False,
        )


@tool
async def manage_notion_note(
    action: str,
    title: str,
    content_markdown: str,
    summary: str,
    category: str,  # ← 🔥 移除默认值，强制 Agent 传递
    target_page_id: Optional[str] = None,
    force_create: bool = False,  # ← 🔥 新增：强制创建标志
    config: RunnableConfig = None,
) -> str:
    """
    Notion 读写的核心工具 - 自动同步到向量库

    ⚠️ 重要规则:
    1. 创建新笔记前，会自动检查是否存在相似内容 (相似度阈值: 0.85)
    2. 必须根据内容指定正确的 category，不能省略
    3. 如果发现相似内容，会返回提示而不是直接创建
    4. 支持事务回滚 (向量同步失败会删除 Notion 页面)

    Args:
        action: 操作类型
            - "create": 创建新笔记 (会自动查重)
            - "overwrite": 覆盖现有笔记 (需要 target_page_id)

        title: 笔记标题

        content_markdown: Markdown 格式的笔记内容

        summary: 内容摘要 (用于查重和向量索引)

        category: 笔记分类 (必填！)
            - "Spanish": 西班牙语学习内容 (语法、词汇、练习等)
            - "Tech": 技术内容 (编程、工具、框架等)
            - "Humanities": 人文内容 (历史、哲学、文学等)
            - "General": 其他内容 (仅当无法分类时使用)

        target_page_id: 目标页面 ID (overwrite 时必填)

        force_create: 是否强制创建 (跳过查重，默认 False)
            - True: 即使发现相似内容也创建新笔记
            - False: 发现相似内容时返回提示

    Returns:
        JSON 格式的操作结果:
        - status: "success" | "duplicate_detected" | "error" | "warning"
        - message: 操作信息
        - page_id: Notion 页面 ID (成功时)
        - url: Notion 页面 URL (成功时)

    Examples:
        # 创建西班牙语笔记 (会自动查重)
        manage_notion_note(
            action="create",
            title="西班牙语动词变位规则",
            content_markdown="ser, estar, tener...",
            summary="动词变位总结",
            category="Spanish"  # ← 必须指定
        )

        # 覆盖现有笔记
        manage_notion_note(
            action="overwrite",
            title="更新的标题",
            content_markdown="更新的内容...",
            summary="更新摘要",
            category="Spanish",
            target_page_id="abc-123-def"
        )

        # 强制创建 (跳过查重)
        manage_notion_note(
            action="create",
            title="类似的标题",
            content_markdown="...",
            summary="...",
            category="Spanish",
            force_create=True  # ← 跳过查重
        )
    """

    # ═══════════════════════════════════════════════════════
    # 🛡️ 步骤 0: 参数验证（防止AI编造内容）
    # ═══════════════════════════════════════════════════════
    from tools.validation import validate_notion_params

    validation_error = validate_notion_params(
        content_markdown=content_markdown,
        title=title,
        action=action,
        min_content_length=10,  # 最少10个字符
    )

    if validation_error:
        print(f"⚠️ [Tool] 参数验证失败: {validation_error[:100]}...")
        return validation_error  # AI 会看到这个消息并询问用户

    print(f"✍️ [Tool] 动作: {action.upper()} | 标题: {title}")

    # =============================
    # 1. 验证分类参数
    # =============================
    valid_categories = ["Spanish", "Tech", "Humanities", "General"]
    if category not in valid_categories:
        return json.dumps(
            {
                "status": "error",
                "message": f"❌ 无效的分类: '{category}'\n"
                f"有效分类: {', '.join(valid_categories)}\n"
                f"请根据笔记内容选择正确的分类。",
            },
            ensure_ascii=False,
        )

    # 记录 General 分类的使用 (用于监控)
    if category == "General":
        print("⚠️ [Tool] 使用了 General 分类，请确认是否正确")

    # =============================
    # 2. 获取服务实例
    # =============================
    configurable = config.get("configurable", {}) if config else {}
    notion_service = configurable.get("notion_service")
    db_ids = configurable.get("db_ids", {})

    if not notion_service:
        notion_service = container.notion_service()

    vector_store = container.vector_store()

    # =============================
    # 3. 🔥 自动查重机制
    # =============================
    if action == "create" and not force_create:
        print("🔍 [Tool] 检查是否存在相似内容...")

        # 使用标题和摘要进行查重
        search_query = f"{title} {summary}"

        try:
            check_result = await asyncio.to_thread(
                vector_store.search_memory,
                search_query,
                n_results=3,
                domain="All",  # 跨所有数据库查重
            )

            if check_result.get("match"):
                similar_score = check_result.get("distance", 0.0)
                similar_title = check_result.get("title", "")
                similar_page_id = check_result.get("page_id", "")
                similar_domain = check_result.get("domain", "")

                # 相似度阈值: 0.85 (可调整)
                # 分数越高越相似 (1.0 = 完全相同)
                if similar_score > 0.85:
                    print(
                        f"⚠️ [Tool] 发现相似内容: {similar_title} (分数: {similar_score:.2f})"
                    )

                    return json.dumps(
                        {
                            "status": "duplicate_detected",
                            "message": f"⚠️ 发现相似内容！\n\n"
                            f"📄 相似笔记: {similar_title}\n"
                            f"📊 相似度: {similar_score:.2f} (>0.85)\n"
                            f"📁 分类: {similar_domain}\n"
                            f"🔗 页面ID: {similar_page_id}\n\n"
                            f"💡 建议操作:\n"
                            f"1. 如果要覆盖旧内容: action='overwrite', target_page_id='{similar_page_id}'\n"
                            f"2. 如果确实要创建新笔记: force_create=True\n"
                            f"3. 如果内容不同: 请修改标题以区分",
                            "similar_page_id": similar_page_id,
                            "similar_title": similar_title,
                            "similar_score": similar_score,
                            "similar_domain": similar_domain,
                        },
                        ensure_ascii=False,
                    )

            print("✅ [Tool] 未发现重复内容，继续创建")

        except Exception as check_error:
            print(f"⚠️ [Tool] 查重失败 (继续创建): {check_error}")
            # 查重失败不阻止创建，但记录日志

    # =============================
    # 4. 执行 Notion 操作
    # =============================
    target_db_id = db_ids.get(category, db_ids.get("General"))
    current_page_id = None
    is_new_page = False

    try:
        if action == "overwrite":
            # 覆盖现有页面
            if not target_page_id:
                return json.dumps(
                    {"status": "error", "message": "❌ 错误: 重写操作必须提供 target_page_id"},
                    ensure_ascii=False,
                )

            print(f"📝 [Tool] 覆盖页面: {target_page_id}")
            success = await asyncio.to_thread(
                notion_service.overwrite_page_content,
                target_page_id,
                content_markdown,
                summary,
            )

            if success:
                current_page_id = target_page_id
            else:
                return json.dumps(
                    {"status": "error", "message": "❌ 无法重写 Notion 页面，页面可能已被删除或权限不足。"},
                    ensure_ascii=False,
                )

        else:
            # 创建新页面
            print("📄 [Tool] 创建新页面...")

            # 🔥 把 summary 作为引用块添加到内容开头
            content_with_summary = f"""
> 📝 **摘要**: {summary}

---

{content_markdown}
"""

            blocks = markdown_to_blocks(content_with_summary)
            response = await asyncio.to_thread(
                notion_service.create_page,
                title=title,
                children=blocks,
                db_id=target_db_id,
                category=category,  # 🔥 设置 Type
                tags=[category, "AI生成"] if category else ["AI生成"],  # 🔥 设置 Tags
            )
            current_page_id = response.get("id")

            if current_page_id:
                is_new_page = True
                print(f"✅ [Tool] Notion 页面已创建: {current_page_id}")

        # =============================
        # 5. 向量库同步 + 事务保证
        # =============================
        if current_page_id:
            print("💾 [Tool] 正在同步到向量库...")

            try:
                # 构建完整的语义文本 (用于向量索引)
                full_semantic_text = (
                    f"Title: {title}\n"
                    f"Summary: {summary}\n"
                    f"Category: {category}\n\n"
                    f"{content_markdown}"
                )

                # 添加到向量库
                await asyncio.to_thread(
                    vector_store.add_memory,
                    page_id=current_page_id,
                    text=full_semantic_text,
                    title=title,
                    domain=category,  # ← 使用 category 作为 domain
                    metadata={
                        "summary": summary,
                        "category": category,
                        "action": action,
                    },
                )

                print("✅ [Tool] 向量库同步成功")

                # 成功响应
                return json.dumps(
                    {
                        "status": "success",
                        "message": "✅ 成功！笔记已保存并索引。",
                        "page_id": current_page_id,
                        "category": category,
                        "url": f"https://www.notion.so/{current_page_id.replace('-', '')}",
                        "action": action,
                    },
                    ensure_ascii=False,
                )

            except Exception as vec_error:
                # 向量同步失败 → 事务回滚
                print(f"❌ [Tool] 向量同步失败: {vec_error}")
                print("🔄 [Tool] 正在执行事务回滚...")

                if is_new_page:
                    # 删除刚创建的 Notion 页面
                    try:
                        await asyncio.to_thread(
                            notion_service.delete_page, current_page_id
                        )
                        print("✅ [Tool] 已回滚并删除 Notion 页面")

                        return json.dumps(
                            {
                                "status": "error",
                                "message": "❌ 事务失败：向量库同步出错，已回滚并删除 Notion 页面以保持一致性。",
                                "error": str(vec_error),
                            },
                            ensure_ascii=False,
                        )

                    except Exception as rollback_error:
                        return json.dumps(
                            {
                                "status": "error",
                                "message": f"❌ 严重错误：向量同步失败且回滚失败！\n"
                                f"Notion 页面 {current_page_id} 可能需要手动删除。",
                                "error": str(vec_error),
                                "rollback_error": str(rollback_error),
                            },
                            ensure_ascii=False,
                        )

                else:
                    # 覆盖操作失败 (不能删除页面)
                    return json.dumps(
                        {
                            "status": "warning",
                            "message": "⚠️ 警告：Notion 已更新，但向量库同步失败，检索功能可能受限。",
                            "page_id": current_page_id,
                            "error": str(vec_error),
                        },
                        ensure_ascii=False,
                    )

    except Exception as e:
        # Notion 操作失败
        print(f"❌ [Tool] Notion 操作失败: {e}")
        return json.dumps(
            {"status": "error", "message": f"❌ 系统错误: {str(e)}"}, ensure_ascii=False
        )

    # 不应该到达这里
    return json.dumps(
        {"status": "error", "message": "❌ 保存失败 (未知错误)。"}, ensure_ascii=False
    )


@tool
async def convert_text_to_audio(text: str, language: str = "es"):
    """
    将文本转换为语音

    Args:
        text: 要转换的文本
        language: 语言代码 (默认 "es" 西班牙语)

    Returns:
        音频文件 URL 或错误信息
    """
    try:
        audio_service = container.audio_service()
        audio_url = await audio_service.generate_audio_file(text, language)

        if audio_url:
            return f"✅ 音频已生成！[AUDIO_URL: {os.path.basename(audio_url)}]"

        return "❌ 语音生成失败。"

    except Exception as e:
        return f"❌ 语音服务错误: {e}"


@tool
async def save_current_file_to_notion(
    file_id: str, summary: str, title: str, config: RunnableConfig = None
):
    """
    将当前上传的文件存档至 Notion

    Args:
        file_id: 文件 ID (Redis 缓存 key)
        summary: 文件摘要
        title: 笔记标题

    Returns:
        操作结果
    """
    print(f"🤖 [Tool] 正在自动存档文件: {file_id}")

    cache = container.cache_wrapper()
    full_text = cache.get(file_id)

    if not full_text:
        return "❌ 错误：文件内容已过期或不存在 (Redis Miss)。"

    configurable = config.get("configurable", {}) if config else {}
    notion_service = configurable.get("notion_service")

    if not notion_service:
        notion_service = container.notion_service()

    db_ids = configurable.get("db_ids", {})
    vector_store = container.vector_store()

    try:
        blocks = markdown_to_blocks(full_text)
        res = await asyncio.to_thread(
            notion_service.create_page, title, blocks, db_id=db_ids.get("Tech")
        )
        page_id = res.get("id")

        if page_id:
            try:
                await asyncio.to_thread(
                    vector_store.add_memory,
                    page_id=page_id,
                    text=full_text,
                    title=title,
                    domain="Tech",
                    metadata={"summary": summary},
                )
                return f"✅ 存档成功！ID: {page_id}"

            except Exception:
                # 向量同步失败 → 回滚
                await asyncio.to_thread(notion_service.delete_page, page_id)
                return "❌ 存档失败：向量索引出错，Notion 页面已回滚。"

    except Exception as e:
        return f"❌ 工具执行错误: {str(e)}"

    return "❌ 存档失败。"


# =============================
# 导入新工具
# =============================
from tools.block_operation_tools import block_operation_tools  # noqa: E402
from tools.conversational_search_tool import conversational_search  # noqa: E402

# =============================
# 工具列表
# =============================
tools_list = [
    conversational_search,  # Week 6-7: 对话式搜索
    search_knowledge_base,  # 轻量级查重
    manage_notion_note,  # Notion 读写 (已修复)
    save_current_file_to_notion,  # 文件存档
    convert_text_to_audio,  # 文本转语音
    *block_operation_tools,  # Week 3-5: Block 操作工具
]
