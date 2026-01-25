"""
tests/unit/test_vector_store.py
测试向量存储的核心逻辑
✅ 修复版本 V2 - 修复单例断言逻辑和 Embedding 数量不匹配导致的 IndexError
"""
from unittest.mock import Mock, patch

import pytest

from vector.vector_store import LevelChunkVectorStore

# =============================================================================
# 简单 Mock 类
# =============================================================================


class SimpleMockPoint:
    def __init__(self, payload: dict, score: float):
        self.payload = payload
        self.score = score
        self.id = "mock_point_id"


class SimpleMockQueryResponse:
    def __init__(self, points: list):
        self.points = points


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_store_instance():
    # 1. 强制重置单例状态
    LevelChunkVectorStore._instance = None
    LevelChunkVectorStore._initialized = False

    # 2. 初始化 Store
    store = LevelChunkVectorStore()

    # 3. 手动注入 Mock
    mock_client = Mock()
    mock_client.upsert.return_value = {"status": "ok"}
    mock_client.delete.return_value = {"status": "ok"}
    mock_client.scroll.return_value = ([], None)
    mock_client.query_points = Mock()
    store._client = mock_client

    mock_emb_provider = Mock()
    mock_emb_provider.embed_query.return_value = [0.1] * 1024

    # 🔥 关键修复：使用 side_effect 动态生成向量
    # 无论 Chunker 生成了多少个分块，这里都会返回相同数量的向量，防止 IndexError
    mock_emb_provider.embed_documents.side_effect = lambda texts: [
        [0.1] * 1024 for _ in texts
    ]

    store._embedding_provider = mock_emb_provider

    # Mock Chunker (模拟真实分块行为)
    mock_chunker = Mock()
    # 模拟返回 2 个分块，以测试批量逻辑
    mock_chunker.chunk_notion_blocks.return_value = [
        Mock(
            chunk_id="c1",
            content="Title",
            level="chapter",
            weight=2.0,
            parent_id=None,
            children_ids=[],
            block_type="h1",
            metadata={},
        ),
        Mock(
            chunk_id="c2",
            content="Content",
            level="paragraph",
            weight=1.0,
            parent_id="c1",
            children_ids=[],
            block_type="p",
            metadata={},
        ),
    ]
    store._chunker = mock_chunker

    return store


# =============================================================================
# Tests
# =============================================================================


class TestVectorStoreSingleton:
    def test_singleton_pattern(self):
        LevelChunkVectorStore._instance = None
        LevelChunkVectorStore._initialized = False
        s1 = LevelChunkVectorStore()
        s2 = LevelChunkVectorStore()
        assert s1 is s2

    def test_singleton_initialization_once(self):
        LevelChunkVectorStore._instance = None
        LevelChunkVectorStore._initialized = False

        s1 = LevelChunkVectorStore()
        # 🔥 关键修复：检查实例属性 s1._initialized，而不是类属性
        assert s1._initialized is True

        s2 = LevelChunkVectorStore()
        assert s1 is s2
        assert s2._initialized is True


class TestVectorStoreAddMemory:
    def test_add_memory_skip_if_exists(self, mock_store_instance):
        mock_pt = SimpleMockPoint(payload={"page_id": "exist"}, score=1.0)
        mock_store_instance.client.scroll.return_value = ([mock_pt], None)

        result = mock_store_instance.add_memory(
            page_id="exist", text="content", skip_if_exists=True
        )
        assert result is False

    def test_add_memory_success(self, mock_store_instance):
        mock_store_instance.client.scroll.return_value = ([], None)

        # 使用 patch 模拟 DOC_STORE
        with patch("vector.vector_store.DOC_STORE") as mock_doc_store:
            mock_doc_store.add_document.return_value = True

            result = mock_store_instance.add_memory(
                page_id="new", text="Long enough content to pass check", title="Title"
            )

            # 🔥 现在应该成功，因为 embed_documents 会返回正确数量的向量
            assert result is True
            mock_doc_store.add_document.assert_called()
            mock_store_instance.client.upsert.assert_called()

    def test_add_memory_skip_short_text(self, mock_store_instance):
        result = mock_store_instance.add_memory(
            page_id="short", text="Hi", title="Short"
        )
        assert result is False


class TestVectorStoreSearch:
    def test_search_memory_basic(self, mock_store_instance):
        mock_pt = SimpleMockPoint(
            payload={
                "title": "T",
                "content": "C",
                "page_id": "p",
                "chunk_id": "c",
                "level": "p",
                "metadata": {},
            },
            score=0.9,
        )
        mock_store_instance.client.query_points.return_value = SimpleMockQueryResponse(
            [mock_pt]
        )

        result = mock_store_instance.search_memory("query")
        assert result["match"] is True

    def test_search_memory_no_results(self, mock_store_instance):
        mock_store_instance.client.query_points.return_value = SimpleMockQueryResponse(
            []
        )
        result = mock_store_instance.search_memory("empty")
        assert result["match"] is False


class TestVectorStoreUtilities:
    def test_delete_by_page_id(self, mock_store_instance):
        with patch("vector.vector_store.DOC_STORE") as mock_doc_store:
            mock_doc_store.delete_document.return_value = True
            result = mock_store_instance.delete_page("del_id")
            assert result is True
            mock_store_instance.client.delete.assert_called()

    def test_page_exists(self, mock_store_instance):
        mock_store_instance.client.scroll.return_value = (
            [SimpleMockPoint({}, 1.0)],
            None,
        )
        assert mock_store_instance.page_exists("p1") is True


class TestVectorStoreLazyLoading:
    def test_client_lazy_loading(self):
        LevelChunkVectorStore._instance = None
        LevelChunkVectorStore._initialized = False
        store = LevelChunkVectorStore()
        assert store._client is None

        with patch("vector.vector_store.QdrantClient") as MockQdrant:
            _ = store.client
            MockQdrant.assert_called()

    def test_embedding_provider_lazy_loading(self):
        LevelChunkVectorStore._instance = None
        LevelChunkVectorStore._initialized = False
        store = LevelChunkVectorStore()
        assert store._embedding_provider is None

        with patch("vector.vector_store.SiliconFlowEmbedding") as MockEmb:
            _ = store.embedding_provider
            MockEmb.assert_called()


class TestVectorStoreErrorHandling:
    def test_add_memory_error_handling(self, mock_store_instance):
        mock_store_instance.client.upsert.side_effect = Exception("Error")
        with patch("vector.vector_store.DOC_STORE"):
            result = mock_store_instance.add_memory("id", "content")
            assert result is False
