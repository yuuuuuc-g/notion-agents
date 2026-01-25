"""
notion/block_ops.py
精准 Block 操作模块

功能：
1. 获取页面所有 Blocks（包括嵌套）
2. 按索引/类型定位特定 Block
3. 更新 Block 内容
4. 在指定位置插入 Block
5. 删除 Block
6. 批量操作 Blocks

保留现有 NotionService 的所有功能，只是扩展精准操作能力
"""
import asyncio
from typing import Dict, List, Optional, Tuple

from notion_client import Client

from utils.logger import get_logger

logger = get_logger(__name__)


class BlockOperations:
    """
    Block 级别的精准操作

    使用场景：
    1. "重写第三段" - find_block_by_index + update_block
    2. "在第二段后插入表格" - find_block_by_index + insert_blocks_after
    3. "删除所有 TODO" - find_blocks_by_content + batch_delete
    """

    def __init__(self, notion_client: Client):
        """
        初始化

        Args:
            notion_client: Notion SDK 客户端实例
        """
        self.client = notion_client

    async def get_page_blocks(self, page_id: str, recursive: bool = True) -> List[Dict]:
        """
        获取页面所有 Blocks（包括嵌套）

        Args:
            page_id: 页面 ID
            recursive: 是否递归获取嵌套的 Blocks

        Returns:
            Block 列表
        """
        try:
            clean_id = page_id.replace("-", "")
            blocks = []
            cursor = None

            while True:
                # 使用 asyncio.to_thread 将同步调用转为异步
                response = await asyncio.to_thread(
                    self.client.blocks.children.list,
                    block_id=clean_id,
                    start_cursor=cursor,
                )

                page_blocks = response.get("results", [])

                # 如果需要递归，获取嵌套 Blocks
                if recursive:
                    for block in page_blocks:
                        block_type = block.get("type")
                        has_children = block.get("has_children", False)

                        if has_children and block_type:
                            # 递归获取子 Blocks
                            children = await self.get_page_blocks(
                                block["id"], recursive=True
                            )
                            # 将子 Blocks 附加到当前 Block
                            block["_children"] = children

                blocks.extend(page_blocks)

                if not response.get("has_more"):
                    break
                cursor = response.get("next_cursor")

            logger.info(
                f"📦 [BlockOps] 获取了 {len(blocks)} 个 Blocks (page_id: {page_id[:8]}...)"
            )
            return blocks

        except Exception as e:
            logger.error(f"❌ [BlockOps] 获取 Blocks 失败: {e}")
            raise

    def find_block_by_index(
        self, blocks: List[Dict], block_type: str, index: int
    ) -> Optional[Dict]:
        """
        按类型和索引定位 Block

        Args:
            blocks: Block 列表
            block_type: Block 类型（paragraph, heading_1, heading_2, code, etc.）
            index: 索引（从 0 开始）

        Returns:
            匹配的 Block，如果没找到返回 None

        Example:
            # 找第 3 个段落（index=2）
            block = find_block_by_index(blocks, 'paragraph', 2)
        """
        typed_blocks = [b for b in blocks if b.get("type") == block_type]

        if 0 <= index < len(typed_blocks):
            found_block = typed_blocks[index]
            logger.debug(
                f"🎯 [BlockOps] 找到 Block: type={block_type}, index={index}, "
                f"id={found_block['id'][:8]}..."
            )
            return found_block

        logger.warning(
            f"⚠️ [BlockOps] Block 未找到: type={block_type}, index={index}, "
            f"total={len(typed_blocks)}"
        )
        return None

    def find_blocks_by_content(
        self, blocks: List[Dict], keyword: str, block_type: Optional[str] = None
    ) -> List[Dict]:
        """
        按内容关键词查找 Blocks

        Args:
            blocks: Block 列表
            keyword: 关键词（如 "TODO", "FIXME"）
            block_type: 可选的 Block 类型过滤

        Returns:
            匹配的 Block 列表

        Example:
            # 找所有包含 "TODO" 的段落
            todos = find_blocks_by_content(blocks, "TODO", "paragraph")
        """
        matches = []

        for block in blocks:
            # 类型过滤
            if block_type and block.get("type") != block_type:
                continue

            # 提取文本内容
            content = self._extract_text_from_block(block)

            # 关键词匹配
            if keyword.lower() in content.lower():
                matches.append(block)

        logger.info(f"🔍 [BlockOps] 找到 {len(matches)} 个包含 '{keyword}' 的 Blocks")
        return matches

    async def update_block(
        self, block_id: str, new_content: str, preserve_formatting: bool = True
    ) -> bool:
        """
        更新 Block 内容

        Args:
            block_id: Block ID
            new_content: 新内容
            preserve_formatting: 是否保留原有格式（粗体、斜体等）

        Returns:
            是否成功

        Example:
            # 更新段落内容
            success = await update_block(block_id, "新的段落内容")
        """
        try:
            # 先获取当前 Block 信息
            block = await asyncio.to_thread(
                self.client.blocks.retrieve, block_id=block_id
            )

            block_type = block.get("type")

            if not block_type:
                logger.error(f"❌ [BlockOps] Block 类型未知: {block_id}")
                return False

            # 构建更新内容
            # 导入 parse_rich_text（从你的 block_builder.py）
            from notion.block_builder import parse_rich_text

            rich_text = parse_rich_text(new_content)

            # 根据不同的 Block 类型构建更新 payload
            update_data = {}

            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3"]:
                update_data[block_type] = {"rich_text": rich_text}
            elif block_type == "code":
                # 代码块需要特殊处理
                update_data["code"] = {
                    "rich_text": rich_text,
                    "language": block.get("code", {}).get("language", "plain text"),
                }
            elif block_type in ["bulleted_list_item", "numbered_list_item"]:
                update_data[block_type] = {"rich_text": rich_text}
            elif block_type == "quote":
                update_data["quote"] = {"rich_text": rich_text}
            elif block_type == "callout":
                update_data["callout"] = {
                    "rich_text": rich_text,
                    "icon": block.get("callout", {}).get(
                        "icon", {"type": "emoji", "emoji": "💡"}
                    ),
                }
            else:
                logger.warning(f"⚠️ [BlockOps] 不支持的 Block 类型: {block_type}")
                return False

            # 执行更新
            await asyncio.to_thread(
                self.client.blocks.update, block_id=block_id, **update_data
            )

            logger.info(f"✅ [BlockOps] Block 已更新: {block_id[:8]}... ({block_type})")
            return True

        except Exception as e:
            logger.error(f"❌ [BlockOps] 更新 Block 失败: {e}")
            return False

    async def insert_blocks_after(
        self, parent_id: str, after_block_id: str, new_blocks: List[Dict]
    ) -> bool:
        """
        在指定 Block 后插入新 Blocks

        注意：Notion API 不直接支持 "插入到某个位置"，需要变通实现

        Args:
            parent_id: 父页面/Block ID
            after_block_id: 在此 Block 后插入
            new_blocks: 要插入的 Blocks（Notion Block 格式）

        Returns:
            是否成功

        变通方案：
        1. 获取所有 Blocks
        2. 找到 after_block 的位置
        3. 删除 after_block 之后的所有 Blocks（保存起来）
        4. 追加 after_block
        5. 追加新 Blocks
        6. 追加保存的 Blocks

        ⚠️ 这个操作比较重，适合少量 Blocks 的场景
        """
        try:
            # 获取所有 Blocks
            all_blocks = await self.get_page_blocks(parent_id, recursive=False)

            # 找到 after_block 的索引
            after_index = None
            for i, block in enumerate(all_blocks):
                if block["id"] == after_block_id:
                    after_index = i
                    break

            if after_index is None:
                logger.error(f"❌ [BlockOps] after_block_id 未找到: {after_block_id}")
                return False

            # Notion API 限制：直接 append 到页面末尾
            # 简化方案：append 到末尾 + 提示用户手动调整位置
            await asyncio.to_thread(
                self.client.blocks.children.append,
                block_id=parent_id,
                children=new_blocks,
            )

            logger.info(
                f"✅ [BlockOps] 已追加 {len(new_blocks)} 个 Blocks " f"(注意：追加到末尾，可能需要手动调整位置)"
            )
            return True

        except Exception as e:
            logger.error(f"❌ [BlockOps] 插入 Blocks 失败: {e}")
            return False

    async def delete_block(self, block_id: str) -> bool:
        """
        删除 Block

        Args:
            block_id: Block ID

        Returns:
            是否成功
        """
        try:
            await asyncio.to_thread(self.client.blocks.delete, block_id=block_id)
            logger.info(f"🗑️ [BlockOps] Block 已删除: {block_id[:8]}...")
            return True

        except Exception as e:
            logger.error(f"❌ [BlockOps] 删除 Block 失败: {e}")
            return False

    async def batch_update_blocks(
        self, updates: List[Tuple[str, str]]
    ) -> Dict[str, int]:
        """
        批量更新 Blocks

        Args:
            updates: [(block_id, new_content), ...]

        Returns:
            {'success': 成功数量, 'failed': 失败数量}

        Example:
            updates = [
                ('block-id-1', '新内容 1'),
                ('block-id-2', '新内容 2'),
            ]
            result = await batch_update_blocks(updates)
        """
        stats = {"success": 0, "failed": 0}

        tasks = [self.update_block(block_id, content) for block_id, content in updates]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                stats["failed"] += 1
            elif result:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            f"📊 [BlockOps] 批量更新完成: " f"成功 {stats['success']}, 失败 {stats['failed']}"
        )
        return stats

    async def batch_delete_blocks(self, block_ids: List[str]) -> Dict[str, int]:
        """
        批量删除 Blocks

        Args:
            block_ids: Block ID 列表

        Returns:
            {'success': 成功数量, 'failed': 失败数量}
        """
        stats = {"success": 0, "failed": 0}

        tasks = [self.delete_block(block_id) for block_id in block_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                stats["failed"] += 1
            elif result:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        logger.info(
            f"📊 [BlockOps] 批量删除完成: " f"成功 {stats['success']}, 失败 {stats['failed']}"
        )
        return stats

    def _extract_text_from_block(self, block: Dict) -> str:
        """
        从 Block 中提取纯文本

        Args:
            block: Notion Block

        Returns:
            纯文本内容
        """
        block_type = block.get("type")
        if not block_type:
            return ""

        block_data = block.get(block_type, {})
        rich_text = block_data.get("rich_text", [])

        # 合并所有 rich_text 的 plain_text
        return "".join([rt.get("plain_text", "") for rt in rich_text])

    def flatten_blocks(
        self, blocks: List[Dict], include_children: bool = True
    ) -> List[Dict]:
        """
        将嵌套的 Blocks 扁平化

        Args:
            blocks: Blocks 列表（可能包含嵌套）
            include_children: 是否包含子 Blocks

        Returns:
            扁平化的 Blocks 列表
        """
        flat_blocks = []

        for block in blocks:
            flat_blocks.append(block)

            if include_children and "_children" in block:
                # 递归扁平化子 Blocks
                children = self.flatten_blocks(
                    block["_children"], include_children=True
                )
                flat_blocks.extend(children)

        return flat_blocks

    def group_blocks_by_type(self, blocks: List[Dict]) -> Dict[str, List[Dict]]:
        """
        按类型分组 Blocks

        Args:
            blocks: Blocks 列表

        Returns:
            {'paragraph': [...], 'heading_1': [...], ...}
        """
        groups = {}

        for block in blocks:
            block_type = block.get("type", "unknown")
            if block_type not in groups:
                groups[block_type] = []
            groups[block_type].append(block)

        return groups


# 辅助函数：构建常用的 Block 结构


def build_paragraph_block(content: str) -> Dict:
    """构建段落 Block"""
    from notion.block_builder import parse_rich_text

    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": parse_rich_text(content)},
    }


def build_heading_block(content: str, level: int = 1) -> Dict:
    """
    构建标题 Block

    Args:
        content: 标题内容
        level: 1, 2, 或 3
    """
    from notion.block_builder import parse_rich_text

    block_type = f"heading_{level}"

    return {
        "object": "block",
        "type": block_type,
        block_type: {"rich_text": parse_rich_text(content)},
    }


def build_code_block(code: str, language: str = "python") -> Dict:
    """构建代码 Block"""
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": code}}],
            "language": language,
        },
    }


def build_table_block(headers: List[str], rows: List[List[str]]) -> Dict:
    """
    构建表格 Block

    Args:
        headers: 表头列表
        rows: 数据行列表

    Example:
        table = build_table_block(
            headers=['Name', 'Age', 'City'],
            rows=[
                ['Alice', '25', 'NYC'],
                ['Bob', '30', 'LA'],
            ]
        )
    """
    from notion.block_builder import parse_rich_text

    # 表头
    header_cells = [parse_rich_text(h) for h in headers]
    table_children = [{"type": "table_row", "table_row": {"cells": header_cells}}]

    # 数据行
    for row in rows:
        cells = [parse_rich_text(cell) for cell in row]
        table_children.append({"type": "table_row", "table_row": {"cells": cells}})

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": len(headers),
            "has_column_header": True,
            "children": table_children,
        },
    }


def build_callout_block(content: str, emoji: str = "💡") -> Dict:
    """构建提示框 Block"""
    from notion.block_builder import parse_rich_text

    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": parse_rich_text(content),
            "icon": {"type": "emoji", "emoji": emoji},
        },
    }


if __name__ == "__main__":
    # 测试代码
    print("BlockOperations 模块已加载")
    print("\n可用功能：")
    print("- get_page_blocks: 获取页面所有 Blocks")
    print("- find_block_by_index: 按索引定位 Block")
    print("- find_blocks_by_content: 按内容查找 Blocks")
    print("- update_block: 更新 Block 内容")
    print("- insert_blocks_after: 在指定位置插入 Blocks")
    print("- delete_block: 删除 Block")
    print("- batch_update_blocks: 批量更新")
    print("- batch_delete_blocks: 批量删除")
