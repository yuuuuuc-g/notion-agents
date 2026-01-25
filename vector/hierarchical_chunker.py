"""
vector/hierarchical_chunker.py
层次化分块器 - 保留文档结构的智能切分

核心改进：
1. 识别 Notion Block 类型（heading_1, heading_2, paragraph, list, code）
2. 保留父子关系（章节 → 小节 → 段落）
3. 权重分配（标题权重高，搜索时优先匹配）
4. 上下文保留（返回完整章节，不是碎片）
"""
import hashlib
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HierarchicalChunk:
    """层次化分块数据结构"""

    chunk_id: str  # 唯一 ID
    content: str  # 文本内容
    level: str  # 层级：chapter/section/paragraph/list/code
    weight: float  # 搜索权重（1.0-2.0）
    parent_id: Optional[str]  # 父块 ID
    children_ids: List[str]  # 子块 ID 列表
    block_type: str  # Notion Block 类型
    metadata: Dict  # 额外元数据


class HierarchicalChunker:
    """
    层次化分块器

    使用场景：
    1. Notion 页面同步时，保留文档结构
    2. 搜索时，返回完整章节而非碎片
    3. 支持按层级过滤（只搜索标题、只搜索代码块等）
    """

    # 权重配置
    WEIGHTS = {
        "heading_1": 2.0,  # 一级标题：最高权重
        "heading_2": 1.7,  # 二级标题
        "heading_3": 1.5,  # 三级标题
        "paragraph": 1.0,  # 段落：基准权重
        "bulleted_list_item": 0.9,  # 列表
        "numbered_list_item": 0.9,
        "code": 1.3,  # 代码块：技术内容权重高
        "quote": 1.1,  # 引用
        "callout": 1.2,  # 提示框
    }

    # 内容长度阈值（过短的块会被合并）
    MIN_CHUNK_LENGTH = 5  # 降低阈值，保留短标题

    def __init__(self):
        self.chunks: List[HierarchicalChunk] = []
        self.current_chapter: Optional[HierarchicalChunk] = None
        self.current_section: Optional[HierarchicalChunk] = None
        self.current_subsection: Optional[HierarchicalChunk] = None

    def chunk_notion_blocks(
        self, blocks: List[Dict], page_id: str, page_title: str = "Untitled"
    ) -> List[HierarchicalChunk]:
        """
        从 Notion Blocks 生成层次化分块

        Args:
            blocks: Notion API 返回的 Block 列表
            page_id: 页面 ID
            page_title: 页面标题

        Returns:
            层次化分块列表
        """
        self.chunks = []
        self.current_chapter = None
        self.current_section = None
        self.current_subsection = None

        # 第一个块：页面标题（作为顶级章节）
        if page_title and page_title != "Untitled":
            title_chunk = self._create_chunk(
                content=page_title,
                block_type="heading_1",
                level="chapter",
                parent_id=None,
                metadata={"page_id": page_id, "is_page_title": True},
            )
            self.chunks.append(title_chunk)
            self.current_chapter = title_chunk

        # 处理所有块
        for block in blocks:
            self._process_block(block, page_id)

        # 过滤掉过短的块
        valid_chunks = [
            c for c in self.chunks if len(c.content.strip()) >= self.MIN_CHUNK_LENGTH
        ]

        logger.info(
            f"📦 [Chunker] {page_title}: "
            f"{len(blocks)} blocks → {len(valid_chunks)} chunks "
            f"(chapters: {sum(1 for c in valid_chunks if c.level == 'chapter')}, "
            f"sections: {sum(1 for c in valid_chunks if c.level == 'section')})"
        )

        return valid_chunks

    def _process_block(self, block: Dict, page_id: str):
        """处理单个 Notion Block"""
        block_type = block.get("type", "paragraph")

        # 提取文本内容
        content = self._extract_text_from_block(block)
        if not content or len(content.strip()) < 5:
            return

        # 根据 Block 类型决定层级
        if block_type == "heading_1":
            chunk = self._create_chunk(
                content=content,
                block_type=block_type,
                level="chapter",
                parent_id=None,
                metadata={"page_id": page_id},
            )
            self.current_chapter = chunk
            self.current_section = None
            self.current_subsection = None

        elif block_type == "heading_2":
            chunk = self._create_chunk(
                content=content,
                block_type=block_type,
                level="section",
                parent_id=self.current_chapter.chunk_id
                if self.current_chapter
                else None,
                metadata={"page_id": page_id},
            )
            self.current_section = chunk
            self.current_subsection = None

            if self.current_chapter:
                self.current_chapter.children_ids.append(chunk.chunk_id)

        elif block_type == "heading_3":
            chunk = self._create_chunk(
                content=content,
                block_type=block_type,
                level="subsection",
                parent_id=self.current_section.chunk_id
                if self.current_section
                else None,
                metadata={"page_id": page_id},
            )
            self.current_subsection = chunk

            if self.current_section:
                self.current_section.children_ids.append(chunk.chunk_id)

        elif block_type == "code":
            # 代码块：特殊处理，权重高
            chunk = self._create_chunk(
                content=content,
                block_type=block_type,
                level="code",
                parent_id=self.current_subsection.chunk_id
                if self.current_subsection
                else (
                    self.current_section.chunk_id
                    if self.current_section
                    else (
                        self.current_chapter.chunk_id if self.current_chapter else None
                    )
                ),
                metadata={
                    "page_id": page_id,
                    "language": block.get("code", {}).get("language", "plain"),
                },
            )
            self._add_to_parent_children(chunk)

        else:
            # 普通段落、列表、引用等
            chunk = self._create_chunk(
                content=content,
                block_type=block_type,
                level="paragraph",
                parent_id=self.current_subsection.chunk_id
                if self.current_subsection
                else (
                    self.current_section.chunk_id
                    if self.current_section
                    else (
                        self.current_chapter.chunk_id if self.current_chapter else None
                    )
                ),
                metadata={"page_id": page_id},
            )
            self._add_to_parent_children(chunk)

        self.chunks.append(chunk)

    def _add_to_parent_children(self, chunk: HierarchicalChunk):
        """将块添加到父块的 children 列表"""
        if chunk.parent_id:
            parent = next(
                (c for c in self.chunks if c.chunk_id == chunk.parent_id), None
            )
            if parent:
                parent.children_ids.append(chunk.chunk_id)

    def _create_chunk(
        self,
        content: str,
        block_type: str,
        level: str,
        parent_id: Optional[str],
        metadata: Dict,
    ) -> HierarchicalChunk:
        """创建一个分块"""
        chunk_id = self._generate_chunk_id(content, block_type)
        weight = self.WEIGHTS.get(block_type, 1.0)

        return HierarchicalChunk(
            chunk_id=chunk_id,
            content=content,
            level=level,
            weight=weight,
            parent_id=parent_id,
            children_ids=[],
            block_type=block_type,
            metadata=metadata,
        )

    def _generate_chunk_id(self, content: str, block_type: str) -> str:
        """生成唯一的 chunk ID"""
        # 使用内容哈希 + 随机 UUID 确保唯一性
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{block_type}_{content_hash}_{uuid.uuid4().hex[:8]}"

    def _extract_text_from_block(self, block: Dict) -> str:
        """从 Notion Block 中提取文本"""
        block_type = block.get("type", "paragraph")

        try:
            # 根据不同的 Block 类型提取文本
            if block_type.startswith("heading"):
                rich_text = block.get(block_type, {}).get("rich_text", [])
            elif block_type == "paragraph":
                rich_text = block.get("paragraph", {}).get("rich_text", [])
            elif block_type == "code":
                rich_text = block.get("code", {}).get("rich_text", [])
                # 代码块保留换行
                return "\n".join([rt.get("plain_text", "") for rt in rich_text])
            elif block_type in ["bulleted_list_item", "numbered_list_item"]:
                rich_text = block.get(block_type, {}).get("rich_text", [])
            elif block_type == "quote":
                rich_text = block.get("quote", {}).get("rich_text", [])
            elif block_type == "callout":
                rich_text = block.get("callout", {}).get("rich_text", [])
            else:
                # 未知类型，尝试通用提取
                rich_text = block.get(block_type, {}).get("rich_text", [])

            # 合并所有 rich_text
            return " ".join([rt.get("plain_text", "") for rt in rich_text])

        except Exception as e:
            logger.warning(f"⚠️ [Chunker] Failed to extract text from block: {e}")
            return ""

    def get_chunk_with_context(
        self, chunk_id: str, include_parent: bool = True, include_children: bool = True
    ) -> Dict[str, any]:
        """
        获取带上下文的分块

        Args:
            chunk_id: 分块 ID
            include_parent: 是否包含父块
            include_children: 是否包含子块

        Returns:
            {
                'chunk': 当前块,
                'parent': 父块（如果有）,
                'children': 子块列表（如果有）,
                'full_context': 完整上下文文本
            }
        """
        chunk = next((c for c in self.chunks if c.chunk_id == chunk_id), None)
        if not chunk:
            return None

        result = {"chunk": chunk}
        context_parts = [chunk.content]

        # 添加父块
        if include_parent and chunk.parent_id:
            parent = next(
                (c for c in self.chunks if c.chunk_id == chunk.parent_id), None
            )
            if parent:
                result["parent"] = parent
                context_parts.insert(0, f"[{parent.level.upper()}] {parent.content}")

        # 添加子块
        if include_children and chunk.children_ids:
            children = [c for c in self.chunks if c.chunk_id in chunk.children_ids]
            result["children"] = children
            for child in children:
                context_parts.append(f"  - {child.content}")

        result["full_context"] = "\n".join(context_parts)

        return result


# 辅助函数：从 Markdown 创建层次化分块（用于文件上传场景）
def chunk_markdown_hierarchically(
    markdown_text: str, doc_id: str, title: str = "Untitled"
) -> List[HierarchicalChunk]:
    """
    从 Markdown 文本创建层次化分块

    用于文件上传场景，将 Markdown 转换为类似 Notion Block 的结构
    """
    chunker = HierarchicalChunker()

    # 简单的 Markdown 解析
    lines = markdown_text.strip().split("\n")
    blocks = []

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # 跳过空行
        if not line:
            i += 1
            continue

        # 一级标题
        if line.startswith("# ") and not line.startswith("## "):
            blocks.append(
                {
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"plain_text": line[2:].strip()}]},
                }
            )
            i += 1

        # 二级标题
        elif line.startswith("## ") and not line.startswith("### "):
            blocks.append(
                {
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"plain_text": line[3:].strip()}]},
                }
            )
            i += 1

        # 三级标题
        elif line.startswith("### "):
            blocks.append(
                {
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"plain_text": line[4:].strip()}]},
                }
            )
            i += 1

        # 代码块
        elif line.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # 跳过结束的 ```

            if code_lines:
                blocks.append(
                    {
                        "type": "code",
                        "code": {"rich_text": [{"plain_text": "\n".join(code_lines)}]},
                    }
                )

        # 列表项
        elif line.startswith("- ") or line.startswith("* "):
            blocks.append(
                {
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"plain_text": line[2:].strip()}]
                    },
                }
            )
            i += 1

        # 普通段落
        else:
            # 收集连续的非空行作为一个段落
            para_lines = [line]
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                # 如果遇到空行、标题、列表、代码块，停止
                if (
                    not next_line
                    or next_line.startswith("#")
                    or next_line.startswith("- ")
                    or next_line.startswith("* ")
                    or next_line.startswith("```")
                ):
                    break
                para_lines.append(next_line)
                i += 1

            paragraph_text = " ".join(para_lines)
            if paragraph_text:
                blocks.append(
                    {
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"plain_text": paragraph_text}]},
                    }
                )

    return chunker.chunk_notion_blocks(blocks, doc_id, title)


if __name__ == "__main__":
    # 测试代码
    test_blocks = [
        {
            "type": "heading_1",
            "heading_1": {"rich_text": [{"plain_text": "Introduction"}]},
        },
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "This is the introduction paragraph."}]
            },
        },
        {
            "type": "heading_2",
            "heading_2": {"rich_text": [{"plain_text": "Background"}]},
        },
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"plain_text": "Background information here."}]
            },
        },
    ]

    chunker = HierarchicalChunker()
    chunks = chunker.chunk_notion_blocks(test_blocks, "test-page-id", "Test Page")

    for chunk in chunks:
        print(
            f"[{chunk.level}] {chunk.content} (weight: {chunk.weight}, parent: {chunk.parent_id})"
        )
