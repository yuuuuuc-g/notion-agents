"""
tests/services/test_chat_service.py
聊天服务单元测试 (Merged Version)
覆盖核心流式逻辑 + 兼容性非流式逻辑
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.chat_service import ChatService


# 模拟 LangGraph 的 Chunk 对象
class MockChunk:
    def __init__(self, content):
        self.content = content


class TestChatService:
    @pytest.fixture
    def mock_deps(self):
        """准备 ChatService 的依赖"""
        mock_config = MagicMock()
        mock_config.DB_TECH_ID = "db-tech"
        mock_config.DB_SPANISH_ID = "db-spanish"
        mock_config.DB_GENERAL_ID = "db-general"
        mock_config.LLM_MODEL_NAME = "test-model"

        mock_notion = MagicMock()

        mock_llm_factory = MagicMock()
        mock_llm_instance = MagicMock()
        mock_llm_factory.return_value = mock_llm_instance

        mock_cache = MagicMock()

        return mock_config, mock_notion, mock_llm_factory, mock_cache

    @pytest.fixture
    def chat_service(self, mock_deps):
        """初始化 ChatService"""
        config, notion, llm_factory, cache = mock_deps
        return ChatService(config, notion, llm_factory, cache)

    # --- 1. 测试旧的兼容方法 (来自你的原有代码) ---

    @pytest.mark.asyncio
    async def test_process_message_success(self, chat_service):
        """测试 process_message (非流式)"""
        # Mock graph.ainvoke (注意路径是 services.chat_service.graph)
        with patch("services.chat_service.graph") as mock_graph:
            mock_graph.ainvoke = AsyncMock(
                return_value={"messages": [{"content": "Hello World"}]}
            )

            result = await chat_service.process_message("Hi", "t1")

            assert result["messages"][0]["content"] == "Hello World"
            # 验证模型工厂调用
            chat_service.llm_factory.assert_called()

    # --- 2. 测试核心流式方法 (新增的高覆盖率测试) ---

    @pytest.mark.asyncio
    async def test_stream_response_text_flow(self, chat_service):
        """测试纯文本流"""

        async def mock_stream(*args, **kwargs):
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MockChunk(content="Hello")},
            }
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": MockChunk(content=" World")},
            }

        with patch(
            "services.chat_service.graph.astream_events", side_effect=mock_stream
        ):
            chunks = []
            async for chunk in chat_service.stream_response("Hi", "t1", "m1"):
                chunks.append(chunk)

            assert "".join(chunks) == "Hello World"

    @pytest.mark.asyncio
    async def test_stream_response_metadata_parsing(self, chat_service):
        """测试元数据解析 (Notion 卡片)"""

        async def mock_stream_with_tool(*args, **kwargs):
            # 模拟搜索工具返回 JSON
            tool_output = json.dumps(
                {
                    "found": True,
                    "title": "Test Note",
                    "page_id": "page-123",
                    "score": 0.9,
                }
            )
            yield {
                "event": "on_tool_end",
                "name": "search_knowledge_base",
                "data": {"output": tool_output},
            }

        with patch(
            "services.chat_service.graph.astream_events",
            side_effect=mock_stream_with_tool,
        ):
            chunks = []
            async for chunk in chat_service.stream_response("Search", "t1", "m1"):
                chunks.append(chunk)

            # 验证是否生成了隐藏标签
            meta_chunk = chunks[0]
            assert "[KNOWLEDGE_META:" in meta_chunk
            assert "Test Note" in meta_chunk
            assert "0.9" in meta_chunk

    @pytest.mark.asyncio
    async def test_stream_response_error_handling(self, chat_service):
        """测试异常捕获"""

        async def mock_error(*args, **kwargs):
            raise ValueError("Graph Error")
            yield  # 语法需要

        with patch(
            "services.chat_service.graph.astream_events", side_effect=mock_error
        ):
            chunks = []
            async for chunk in chat_service.stream_response("Hi", "t1", "m1"):
                chunks.append(chunk)

            assert "[SYSTEM_ERROR: Graph Error]" in chunks[0]
