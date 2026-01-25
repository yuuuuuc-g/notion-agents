"""
tests/notion/test_block_ops.py
Block 操作模块测试
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 注意：需要先安装依赖
# pip install pytest-asyncio


class TestBlockOperations:
    """测试 BlockOperations 类"""

    def setup_method(self):
        """每个测试前准备"""
        # Mock Notion Client
        self.mock_client = MagicMock()

        # 创建 BlockOperations 实例（延迟导入避免初始化问题）
        from notion.block_ops import BlockOperations

        self.block_ops = BlockOperations(self.mock_client)

    @pytest.mark.asyncio
    async def test_get_page_blocks_simple(self):
        """测试获取页面 Blocks（无嵌套）"""
        # Mock 返回值
        mock_response = {
            "results": [
                {
                    "id": "block-1",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"plain_text": "Text 1"}]},
                },
                {
                    "id": "block-2",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"plain_text": "Heading"}]},
                },
            ],
            "has_more": False,
        }

        # 使用 patch 模拟 asyncio.to_thread
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_response

            blocks = await self.block_ops.get_page_blocks("page-123", recursive=False)

            assert len(blocks) == 2
            assert blocks[0]["type"] == "paragraph"
            assert blocks[1]["type"] == "heading_1"

    def test_find_block_by_index(self):
        """测试按索引查找 Block"""
        blocks = [
            {"id": "p1", "type": "paragraph"},
            {"id": "h1", "type": "heading_1"},
            {"id": "p2", "type": "paragraph"},
            {"id": "p3", "type": "paragraph"},
        ]

        # 找第 1 个段落（index=0）
        block = self.block_ops.find_block_by_index(blocks, "paragraph", 0)
        assert block["id"] == "p1"

        # 找第 2 个段落（index=1）
        block = self.block_ops.find_block_by_index(blocks, "paragraph", 1)
        assert block["id"] == "p2"

        # 找不存在的索引
        block = self.block_ops.find_block_by_index(blocks, "paragraph", 10)
        assert block is None

    def test_find_blocks_by_content(self):
        """测试按内容查找 Blocks"""
        blocks = [
            {
                "id": "b1",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "This is a TODO item"}]},
            },
            {
                "id": "b2",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Normal paragraph"}]},
            },
            {
                "id": "b3",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Another TODO"}]},
            },
        ]

        # 查找包含 "TODO" 的 Blocks
        matches = self.block_ops.find_blocks_by_content(blocks, "TODO")

        assert len(matches) == 2
        assert matches[0]["id"] == "b1"
        assert matches[1]["id"] == "b3"

    @pytest.mark.asyncio
    async def test_update_block_paragraph(self):
        """测试更新段落 Block"""
        # Mock retrieve 返回
        mock_block = {
            "id": "block-123",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"plain_text": "Original text"}]},
        }

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            # 第一次调用返回 Block 信息
            # 第二次调用执行更新
            mock_to_thread.side_effect = [mock_block, None]

            success = await self.block_ops.update_block("block-123", "New text")

            assert success
            assert mock_to_thread.call_count == 2

    def test_extract_text_from_block(self):
        """测试从 Block 提取文本"""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"plain_text": "Hello "},
                    {"plain_text": "World"},
                ]
            },
        }

        text = self.block_ops._extract_text_from_block(block)
        assert text == "Hello World"

    def test_group_blocks_by_type(self):
        """测试按类型分组"""
        blocks = [
            {"type": "paragraph"},
            {"type": "heading_1"},
            {"type": "paragraph"},
            {"type": "code"},
        ]

        groups = self.block_ops.group_blocks_by_type(blocks)

        assert len(groups["paragraph"]) == 2
        assert len(groups["heading_1"]) == 1
        assert len(groups["code"]) == 1

    def test_flatten_blocks(self):
        """测试扁平化嵌套 Blocks"""
        blocks = [
            {
                "id": "b1",
                "type": "paragraph",
                "_children": [
                    {"id": "b1-1", "type": "paragraph"},
                    {"id": "b1-2", "type": "paragraph"},
                ],
            },
            {"id": "b2", "type": "heading_1"},
        ]

        flat_blocks = self.block_ops.flatten_blocks(blocks)

        assert len(flat_blocks) == 4
        assert flat_blocks[0]["id"] == "b1"
        assert flat_blocks[1]["id"] == "b1-1"
        assert flat_blocks[2]["id"] == "b1-2"
        assert flat_blocks[3]["id"] == "b2"


class TestBlockBuilders:
    """测试 Block 构建函数"""

    def test_build_paragraph_block(self):
        """测试构建段落 Block"""
        from notion.block_ops import build_paragraph_block

        block = build_paragraph_block("Hello World")

        assert block["type"] == "paragraph"
        assert block["paragraph"]["rich_text"][0]["text"]["content"] == "Hello World"

    def test_build_heading_block(self):
        """测试构建标题 Block"""
        from notion.block_ops import build_heading_block

        # 一级标题
        block = build_heading_block("Title", level=1)
        assert block["type"] == "heading_1"

        # 二级标题
        block = build_heading_block("Subtitle", level=2)
        assert block["type"] == "heading_2"

    def test_build_code_block(self):
        """测试构建代码 Block"""
        from notion.block_ops import build_code_block

        block = build_code_block("print('hello')", language="python")

        assert block["type"] == "code"
        assert block["code"]["language"] == "python"
        assert "print('hello')" in block["code"]["rich_text"][0]["text"]["content"]

    def test_build_table_block(self):
        """测试构建表格 Block"""
        from notion.block_ops import build_table_block

        block = build_table_block(
            headers=["Name", "Age"],
            rows=[
                ["Alice", "25"],
                ["Bob", "30"],
            ],
        )

        assert block["type"] == "table"
        assert block["table"]["table_width"] == 2
        assert len(block["table"]["children"]) == 3  # 表头 + 2 行

    def test_build_callout_block(self):
        """测试构建提示框 Block"""
        from notion.block_ops import build_callout_block

        block = build_callout_block("Important note", emoji="⚠️")

        assert block["type"] == "callout"
        assert block["callout"]["icon"]["emoji"] == "⚠️"


class TestBlockOperationToolsIntegration:
    """集成测试：完整的工作流"""

    @pytest.mark.skip(reason="需要真实的 Notion API")
    @pytest.mark.asyncio
    async def test_end_to_end_rewrite_block(self):
        """端到端测试：重写 Block"""
        from tools.block_operation_tools import rewrite_block_by_index

        # 使用真实的服务
        result = await rewrite_block_by_index(
            page_id="your-real-page-id",
            block_type="paragraph",
            block_index=0,
            instruction="翻译成英文",
        )

        import json

        result_dict = json.loads(result)

        assert result_dict["success"] is True
        assert "new" in result_dict

    @pytest.mark.skip(reason="需要真实的 Notion API")
    @pytest.mark.asyncio
    async def test_end_to_end_insert_table(self):
        """端到端测试：插入表格"""
        from tools.block_operation_tools import insert_table_after_block

        result = await insert_table_after_block(
            page_id="your-real-page-id",
            after_block_type="paragraph",
            after_block_index=0,
            table_topic="项目进度",
            rows=3,
            cols=3,
        )

        import json

        result_dict = json.loads(result)

        assert result_dict["success"] is True
        assert "table_data" in result_dict


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
