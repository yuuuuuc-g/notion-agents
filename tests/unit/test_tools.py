"""
tests/unit/test_tools.py
测试 LangChain Tools 的实际逻辑
✅ 修复版：使用 .ainvoke() 调用异步工具
"""
import json
from unittest.mock import AsyncMock, patch

import pytest

from tools.tools import convert_text_to_audio, manage_notion_note, search_knowledge_base


@pytest.mark.asyncio
async def test_search_knowledge_base_hit():
    """测试搜索工具命中"""
    # Mock 容器中的 vector_store
    with patch("tools.tools.container") as mock_container:
        mock_vs = mock_container.vector_store.return_value
        mock_vs.search_memory.return_value = {
            "match": True,
            "title": "Test",
            "page_id": "123",
            "metadata": {"content": "content"},
        }

        # ✅ 修复点：使用 ainvoke
        result = await search_knowledge_base.ainvoke("query")

        data = json.loads(result)
        assert data["found"] is True
        assert data["page_id"] == "123"


@pytest.mark.asyncio
async def test_convert_text_to_audio_success():
    """测试音频工具"""
    with patch("tools.tools.container") as mock_container:
        mock_audio = mock_container.audio_service.return_value
        mock_audio.generate_audio_file = AsyncMock(return_value="/path/to/audio.mp3")

        # ✅ 修复点：使用 ainvoke
        result = await convert_text_to_audio.ainvoke({"text": "Hello"})

        assert "AUDIO_URL" in result
        assert "audio.mp3" in result


@pytest.mark.asyncio
async def test_manage_notion_note_create():
    """测试 Notion 笔记创建工具"""
    # 模拟 Config
    mock_config = {"configurable": {"db_ids": {"General": "db-1"}}}

    with patch("tools.tools.container") as mock_container:
        # Mock Notion Service
        mock_notion = mock_container.notion_service.return_value
        mock_notion.create_page.return_value = {"id": "page-new"}

        # Mock Vector Store
        mock_vs = mock_container.vector_store.return_value

        # ✅ 修复点：使用 ainvoke
        result = await manage_notion_note.ainvoke(
            {
                "action": "create",
                "title": "Test Note",
                "content_markdown": "Content",
                "summary": "Summary",
                "category": "General",
            },
            config=mock_config,
        )

        assert "https://www.notion.so/pagenew" in result
        # 验证是否调用了向量库同步
        mock_vs.add_memory.assert_called()
