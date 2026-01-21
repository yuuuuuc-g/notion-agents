"""
tests/unit/test_vector_store.py
向量存储服务单元测试
"""
from unittest.mock import MagicMock, patch

import pytest

from vector.vector_store import LevelChunkVectorStore


@pytest.fixture
def vector_store():
    # Mock 构造函数中用到的类
    with patch("vector.vector_store.QdrantClient"):
        with patch("vector.vector_store.SiliconFlowEmbedding") as MockEmbedClass:
            # 1. 模拟 embedding 实例
            mock_embed_instance = MockEmbedClass.return_value
            # 2. 设置 embed_query 方法的返回值
            mock_embed_instance.embed_query.return_value = [0.1] * 1024

            # 重置单例
            LevelChunkVectorStore._instance = None
            LevelChunkVectorStore._initialized = False
            store = LevelChunkVectorStore(collection_name="test")
            return store


def test_singleton_pattern():
    LevelChunkVectorStore._instance = None
    s1 = LevelChunkVectorStore()
    s2 = LevelChunkVectorStore()
    assert s1 is s2


def test_add_memory_skip_if_exists(vector_store):
    with patch.object(LevelChunkVectorStore, "page_exists", return_value=True):
        result = vector_store.add_memory("p1", "content", skip_if_exists=True)
        assert result is False


def test_search_memory_basic(vector_store):
    # ✅ 修复点：直接使用 fixture 初始化好的 mock 状态
    # (在 fixture 里已经设置了 embed_query.return_value)

    # Mock Qdrant response
    mock_point = MagicMock()
    mock_point.score = 0.9
    mock_point.payload = {"title": "Hit", "parent_id": "p1", "snippet": "text"}

    mock_response = MagicMock()
    mock_response.points = [mock_point]

    # Mock client.query_points
    # client 是 lazy property，我们需要 Mock 它的返回值
    with patch.object(LevelChunkVectorStore, "client") as mock_client_prop:
        # 注意：这里 mock_client_prop 是 property 对象本身，还是 property 返回的值？
        # 在 patch.object 中，如果 target 是属性，它会替换该属性的值。
        # 所以 mock_client_prop 就是 client 实例的 Mock
        mock_client_prop.query_points.return_value = mock_response

        # Mock DOC_STORE
        with patch("vector.vector_store.DOC_STORE") as mock_doc_store:
            mock_doc_store.get_document.return_value = "Full Content"

            result = vector_store.search_memory("query")
            assert result["match"] is True
            assert result["title"] == "Hit"
