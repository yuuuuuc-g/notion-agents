"""
tools/block_operation_tools.py
精准 Block 操作工具集

这些工具是对现有 manage_notion_note 的补充，不是替代
使用场景：需要精准操作时才使用这些工具
"""
import json
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from core.container import container
from notion.block_ops import (
    BlockOperations,
    build_table_block,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@tool
async def rewrite_block_by_index(
    page_id: str,
    block_type: str,
    block_index: int,
    instruction: str,
    config: RunnableConfig = None,
) -> str:
    """
    重写指定的 Block（按类型和索引）

    使用场景：
    - "把第三个段落翻译成英文"
    - "重写第二个标题，使其更简洁"

    Args:
        page_id: 页面 ID（32 位，如 "1234567890abcdef1234567890abcdef"）
        block_type: Block 类型（paragraph, heading_1, heading_2, code 等）
        block_index: 索引（从 0 开始，如 0 表示第一个，2 表示第三个）
        instruction: 重写指令（如 "翻译成英文", "使其更简洁"）

    Returns:
        操作结果（JSON 字符串）

    Example:
        rewrite_block_by_index(
            page_id="abc123...",
            block_type="paragraph",
            block_index=2,  # 第三个段落
            instruction="翻译成英文"
        )
    """
    try:
        # 获取 Notion 服务
        configurable = config.get("configurable", {}) if config else {}
        notion_service = (
            configurable.get("notion_service") or container.notion_service()
        )

        # 创建 BlockOperations 实例
        block_ops = BlockOperations(notion_service.notion)

        # 1. 获取页面所有 Blocks
        blocks = await block_ops.get_page_blocks(page_id, recursive=False)

        # 2. 定位目标 Block
        target_block = block_ops.find_block_by_index(blocks, block_type, block_index)

        if not target_block:
            return json.dumps(
                {
                    "success": False,
                    "error": f"未找到 Block: type={block_type}, index={block_index}",
                    "total_blocks_of_type": len(
                        [b for b in blocks if b.get("type") == block_type]
                    ),
                },
                ensure_ascii=False,
            )

        # 3. 提取原内容
        original_text = block_ops._extract_text_from_block(target_block)

        # 4. 使用 LLM 处理
        llm = container.llm_factory()
        prompt = f"{instruction}\n\n原文：{original_text}"

        response = await llm.ainvoke(prompt)
        new_text = response.content if hasattr(response, "content") else str(response)

        # 5. 更新 Block
        success = await block_ops.update_block(target_block["id"], new_text)

        return json.dumps(
            {
                "success": success,
                "block_id": target_block["id"],
                "block_type": block_type,
                "block_index": block_index,
                "original": original_text[:100] + "..."
                if len(original_text) > 100
                else original_text,
                "new": new_text[:100] + "..." if len(new_text) > 100 else new_text,
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"❌ [Tool] rewrite_block_by_index 失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def insert_table_after_block(
    page_id: str,
    after_block_type: str,
    after_block_index: int,
    table_topic: str,
    rows: int = 3,
    cols: int = 3,
    config: RunnableConfig = None,
) -> str:
    """
    在指定 Block 后插入表格

    使用场景：
    - "在第二段后插入一个 3x3 的表格，主题是项目进度"

    Args:
        page_id: 页面 ID
        after_block_type: 在此类型的 Block 后插入（paragraph, heading_1 等）
        after_block_index: 索引（如 1 表示第二个）
        table_topic: 表格主题（LLM 会基于此生成内容）
        rows: 行数（不包括表头）
        cols: 列数

    Returns:
        操作结果（JSON 字符串）

    Example:
        insert_table_after_block(
            page_id="abc123...",
            after_block_type="paragraph",
            after_block_index=1,  # 第二个段落后
            table_topic="项目进度跟踪",
            rows=3,
            cols=4
        )
    """
    try:
        # 获取服务
        configurable = config.get("configurable", {}) if config else {}
        notion_service = (
            configurable.get("notion_service") or container.notion_service()
        )

        block_ops = BlockOperations(notion_service.notion)

        # 1. 获取页面 Blocks
        blocks = await block_ops.get_page_blocks(page_id, recursive=False)

        # 2. 定位目标 Block
        target_block = block_ops.find_block_by_index(
            blocks, after_block_type, after_block_index
        )

        if not target_block:
            return json.dumps(
                {
                    "success": False,
                    "error": f"未找到 Block: type={after_block_type}, index={after_block_index}",
                },
                ensure_ascii=False,
            )

        # 3. 使用 LLM 生成表格内容
        llm = container.llm_factory()
        prompt = f"""
        创建一个 {rows}x{cols} 的表格，主题是：{table_topic}

        返回 JSON 格式：
        {{
            "headers": ["列1", "列2", ...],
            "rows": [
                ["单元格1", "单元格2", ...],
                ...
            ]
        }}

        只返回 JSON，不要其他内容。
        """

        response = await llm.ainvoke(prompt)
        response_text = (
            response.content if hasattr(response, "content") else str(response)
        )

        # 清理 JSON（移除可能的 ```json 标记）
        response_text = response_text.replace("```json", "").replace("```", "").strip()

        try:
            table_data = json.loads(response_text)
        except json.JSONDecodeError:
            return json.dumps(
                {
                    "success": False,
                    "error": "LLM 返回的不是有效 JSON",
                    "llm_response": response_text[:200],
                },
                ensure_ascii=False,
            )

        # 4. 构建表格 Block
        table_block = build_table_block(
            headers=table_data.get("headers", [f"列{i+1}" for i in range(cols)]),
            rows=table_data.get(
                "rows", [[f"R{i}C{j}" for j in range(cols)] for i in range(rows)]
            ),
        )

        # 5. 插入表格（追加到页面末尾）
        success = await block_ops.insert_blocks_after(
            parent_id=page_id,
            after_block_id=target_block["id"],
            new_blocks=[table_block],
        )

        return json.dumps(
            {
                "success": success,
                "after_block_id": target_block["id"],
                "table_data": table_data,
                "note": "表格已追加到页面末尾（Notion API 限制，无法插入到指定位置）",
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"❌ [Tool] insert_table_after_block 失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def batch_translate_blocks_by_keyword(
    page_id: str,
    keyword: str,
    target_language: str = "en",
    block_type: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """
    批量翻译包含特定关键词的 Blocks

    使用场景：
    - "把所有标记为 TODO 的段落翻译成英文"
    - "翻译所有包含 '待办' 的列表项"

    Args:
        page_id: 页面 ID
        keyword: 关键词（如 "TODO", "待办"）
        target_language: 目标语言（en, zh, es, fr 等）
        block_type: 可选的 Block 类型过滤（paragraph, bulleted_list_item 等）

    Returns:
        操作结果（JSON 字符串）

    Example:
        batch_translate_blocks_by_keyword(
            page_id="abc123...",
            keyword="TODO",
            target_language="en",
            block_type="paragraph"
        )
    """
    try:
        # 获取服务
        configurable = config.get("configurable", {}) if config else {}
        notion_service = (
            configurable.get("notion_service") or container.notion_service()
        )

        block_ops = BlockOperations(notion_service.notion)
        llm = container.llm_factory()

        # 1. 获取页面 Blocks
        blocks = await block_ops.get_page_blocks(page_id, recursive=False)

        # 2. 查找匹配的 Blocks
        matching_blocks = block_ops.find_blocks_by_content(blocks, keyword, block_type)

        if not matching_blocks:
            return json.dumps(
                {
                    "success": True,
                    "translated_count": 0,
                    "message": f"未找到包含 '{keyword}' 的 Blocks",
                },
                ensure_ascii=False,
            )

        # 3. 批量翻译
        updates = []

        for block in matching_blocks:
            original_text = block_ops._extract_text_from_block(block)

            # LLM 翻译
            prompt = f"翻译成 {target_language}（只返回翻译结果）：{original_text}"
            response = await llm.ainvoke(prompt)
            translated = (
                response.content if hasattr(response, "content") else str(response)
            )

            updates.append((block["id"], translated))

        # 4. 批量更新
        result = await block_ops.batch_update_blocks(updates)

        return json.dumps(
            {
                "success": True,
                "keyword": keyword,
                "target_language": target_language,
                "total_found": len(matching_blocks),
                "success_count": result["success"],
                "failed_count": result["failed"],
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"❌ [Tool] batch_translate_blocks_by_keyword 失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def find_and_show_blocks(
    page_id: str,
    keyword: Optional[str] = None,
    block_type: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """
    查找并显示页面中的 Blocks（用于探索）

    使用场景：
    - "显示这个页面的所有段落"
    - "找出所有包含 'bug' 的 Blocks"

    Args:
        page_id: 页面 ID
        keyword: 可选的关键词过滤
        block_type: 可选的类型过滤

    Returns:
        Blocks 列表（JSON 字符串）

    Example:
        find_and_show_blocks(
            page_id="abc123...",
            keyword="bug",
            block_type="paragraph"
        )
    """
    try:
        # 获取服务
        configurable = config.get("configurable", {}) if config else {}
        notion_service = (
            configurable.get("notion_service") or container.notion_service()
        )

        block_ops = BlockOperations(notion_service.notion)

        # 获取 Blocks
        blocks = await block_ops.get_page_blocks(page_id, recursive=False)

        # 过滤
        if keyword:
            blocks = block_ops.find_blocks_by_content(blocks, keyword, block_type)
        elif block_type:
            blocks = [b for b in blocks if b.get("type") == block_type]

        # 构建结果
        results = []
        for i, block in enumerate(blocks):
            results.append(
                {
                    "index": i,
                    "type": block.get("type"),
                    "id": block["id"],
                    "content": block_ops._extract_text_from_block(block)[:200],
                }
            )

        return json.dumps(
            {
                "success": True,
                "total_blocks": len(results),
                "blocks": results[:10],  # 最多返回 10 个
                "note": "如果 Blocks 数量 > 10，只显示前 10 个",
            },
            ensure_ascii=False,
            indent=2,
        )

    except Exception as e:
        logger.error(f"❌ [Tool] find_and_show_blocks 失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


@tool
async def delete_blocks_by_keyword(
    page_id: str,
    keyword: str,
    block_type: Optional[str] = None,
    config: RunnableConfig = None,
) -> str:
    """
    删除包含特定关键词的 Blocks

    ⚠️ 危险操作，请谨慎使用

    Args:
        page_id: 页面 ID
        keyword: 关键词
        block_type: 可选的类型过滤

    Returns:
        操作结果（JSON 字符串）
    """
    try:
        # 获取服务
        configurable = config.get("configurable", {}) if config else {}
        notion_service = (
            configurable.get("notion_service") or container.notion_service()
        )

        block_ops = BlockOperations(notion_service.notion)

        # 查找匹配的 Blocks
        blocks = await block_ops.get_page_blocks(page_id, recursive=False)
        matching_blocks = block_ops.find_blocks_by_content(blocks, keyword, block_type)

        if not matching_blocks:
            return json.dumps(
                {
                    "success": True,
                    "deleted_count": 0,
                    "message": f"未找到包含 '{keyword}' 的 Blocks",
                },
                ensure_ascii=False,
            )

        # 批量删除
        block_ids = [b["id"] for b in matching_blocks]
        result = await block_ops.batch_delete_blocks(block_ids)

        return json.dumps(
            {
                "success": True,
                "keyword": keyword,
                "total_found": len(matching_blocks),
                "success_count": result["success"],
                "failed_count": result["failed"],
            },
            ensure_ascii=False,
        )

    except Exception as e:
        logger.error(f"❌ [Tool] delete_blocks_by_keyword 失败: {e}")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


# 导出所有工具（用于添加到 tools_list）
block_operation_tools = [
    rewrite_block_by_index,
    insert_table_after_block,
    batch_translate_blocks_by_keyword,
    find_and_show_blocks,
    delete_blocks_by_keyword,
]


if __name__ == "__main__":
    print("Block Operation Tools 已加载")
    print("\n可用工具：")
    # 🔥 修改：将 tool 改为 t
    for t in block_operation_tools:
        print(f"- {t.name}: {t.description[:80]}...")
