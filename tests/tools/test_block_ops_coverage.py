"""
tests/tools/test_block_ops_coverage.py
针对 tools/block_operation_tools.py 的高覆盖率测试
修复版 v2: 使用 .ainvoke() 调用 LangChain Tools
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 导入待测工具
from tools.block_operation_tools import (
    batch_translate_blocks_by_keyword,
    delete_blocks_by_keyword,
    find_and_show_blocks,
    insert_table_after_block,
    rewrite_block_by_index,
)

# === Fixtures ===


@pytest.fixture
def mock_deps():
    """Mock 核心依赖"""
    with patch("tools.block_operation_tools.BlockOperations") as MockBlockOps, patch(
        "tools.block_operation_tools.container"
    ) as mock_container:
        block_ops_instance = MockBlockOps.return_value

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value.content = "Mocked LLM Response"
        mock_container.llm_factory.return_value = mock_llm

        mock_notion = MagicMock()
        mock_container.notion_service.return_value = mock_notion

        yield {
            "block_ops": block_ops_instance,
            "llm": mock_llm,
            "container": mock_container,
        }


# === Tests ===


@pytest.mark.asyncio
async def test_rewrite_block_success(mock_deps):
    ops = mock_deps["block_ops"]
    ops.get_page_blocks = AsyncMock(return_value=[{"id": "b1", "type": "paragraph"}])
    ops.find_block_by_index.return_value = {"id": "b1", "type": "paragraph"}
    ops._extract_text_from_block.return_value = "Original Text"
    ops.update_block = AsyncMock(return_value=True)

    # 🔥 修复：使用 ainvoke 传递字典参数
    result_json = await rewrite_block_by_index.ainvoke(
        {
            "page_id": "page_1",
            "block_type": "paragraph",
            "block_index": 0,
            "instruction": "Translate",
        }
    )

    result = json.loads(result_json)
    assert result["success"] is True
    assert result["block_id"] == "b1"


@pytest.mark.asyncio
async def test_rewrite_block_not_found(mock_deps):
    ops = mock_deps["block_ops"]
    ops.get_page_blocks = AsyncMock(return_value=[])
    ops.find_block_by_index.return_value = None

    result_json = await rewrite_block_by_index.ainvoke(
        {
            "page_id": "page_1",
            "block_type": "code",
            "block_index": 5,
            "instruction": "Fix",
        }
    )

    result = json.loads(result_json)
    assert result["success"] is False
    assert "未找到 Block" in result["error"]


@pytest.mark.asyncio
async def test_insert_table_success(mock_deps):
    ops = mock_deps["block_ops"]
    llm = mock_deps["llm"]

    ops.get_page_blocks = AsyncMock(return_value=[{"id": "b1"}])
    ops.find_block_by_index.return_value = {"id": "b1"}

    table_json = json.dumps({"headers": ["A", "B"], "rows": [["1", "2"]]})
    llm.ainvoke.return_value.content = f"```json\n{table_json}\n```"
    ops.insert_blocks_after = AsyncMock(return_value=True)

    result_json = await insert_table_after_block.ainvoke(
        {
            "page_id": "p1",
            "after_block_type": "paragraph",
            "after_block_index": 0,
            "table_topic": "Test",
        }
    )

    result = json.loads(result_json)
    assert result["success"] is True
    ops.insert_blocks_after.assert_called_once()


@pytest.mark.asyncio
async def test_insert_table_invalid_json(mock_deps):
    ops = mock_deps["block_ops"]
    llm = mock_deps["llm"]
    ops.get_page_blocks = AsyncMock(return_value=[{"id": "b1"}])
    ops.find_block_by_index.return_value = {"id": "b1"}
    llm.ainvoke.return_value.content = "Not a JSON"

    result_json = await insert_table_after_block.ainvoke(
        {
            "page_id": "p1",
            "after_block_type": "para",
            "after_block_index": 0,
            "table_topic": "topic",
        }
    )

    result = json.loads(result_json)
    assert result["success"] is False
    assert "不是有效 JSON" in result["error"]


@pytest.mark.asyncio
async def test_batch_translate_success(mock_deps):
    ops = mock_deps["block_ops"]
    blocks = [{"id": "b1"}, {"id": "b2"}]
    ops.get_page_blocks = AsyncMock(return_value=blocks)
    ops.find_blocks_by_content.return_value = blocks
    ops._extract_text_from_block.return_value = "你好"
    ops.batch_update_blocks = AsyncMock(return_value={"success": 2, "failed": 0})

    result_json = await batch_translate_blocks_by_keyword.ainvoke(
        {"page_id": "p1", "keyword": "TODO"}
    )

    result = json.loads(result_json)
    assert result["success"] is True
    assert result["success_count"] == 2


@pytest.mark.asyncio
async def test_find_and_show_blocks(mock_deps):
    ops = mock_deps["block_ops"]
    blocks = [{"id": "b1", "type": "code"}]
    ops.get_page_blocks = AsyncMock(return_value=blocks)
    ops._extract_text_from_block.side_effect = lambda b: "content"

    result_json = await find_and_show_blocks.ainvoke(
        {"page_id": "p1", "block_type": "code"}
    )

    result = json.loads(result_json)
    assert result["success"] is True
    assert len(result["blocks"]) == 1


@pytest.mark.asyncio
async def test_delete_blocks_success(mock_deps):
    ops = mock_deps["block_ops"]
    ops.get_page_blocks = AsyncMock(return_value=[])
    ops.find_blocks_by_content.return_value = [{"id": "b1"}]
    ops.batch_delete_blocks = AsyncMock(return_value={"success": 1, "failed": 0})

    result_json = await delete_blocks_by_keyword.ainvoke(
        {"page_id": "p1", "keyword": "del"}
    )

    result = json.loads(result_json)
    assert result["success"] is True
    assert result["success_count"] == 1
