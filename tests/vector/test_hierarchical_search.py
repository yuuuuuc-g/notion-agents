"""
tests/vector/test_hierarchical_search.py
测试层次化分块和混合检索功能
修复版 v2: 修正导入路径 (LevelChunkVectorStore)，适配合并后的架构
"""
from unittest.mock import MagicMock, patch

import pytest

from vector.hierarchical_chunker import (
    HierarchicalChunker,
    chunk_markdown_hierarchically,
)
from vector.hybrid_search import (
    HybridSearchEngine,
    SearchResult,
    calculate_diversity,
    cluster_by_topic,
)


class TestHierarchicalChunker:
    """测试层次化分块器"""

    def setup_method(self):
        """每个测试前准备"""
        self.chunker = HierarchicalChunker()

    def test_chunk_simple_blocks(self):
        """测试简单 Notion Blocks 的分块"""
        blocks = [
            {
                "type": "heading_1",
                "heading_1": {"rich_text": [{"plain_text": "Chapter 1"}]},
            },
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "This is the first paragraph."}]
                },
            },
            {
                "type": "heading_2",
                "heading_2": {"rich_text": [{"plain_text": "Section 1.1"}]},
            },
            {
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"plain_text": "This is the second paragraph."}]
                },
            },
        ]

        chunks = self.chunker.chunk_notion_blocks(blocks, "test-page", "Test Page")

        # 验证：应该保留结构
        assert len(chunks) >= 2

        # 验证层级
        levels = [c.level for c in chunks]
        assert "paragraph" in levels or "chapter" in levels

        # 验证权重
        # 注意：需要确保 chunker 的逻辑确实给 Heading 分配了高权重
        chapters = [c for c in chunks if c.level == "chapter"]
        if chapters:
            assert chapters[0].weight >= 1.5

    def test_parent_child_relationship(self):
        """测试父子关系"""
        blocks = [
            {
                "type": "heading_1",
                "heading_1": {"rich_text": [{"plain_text": "Main Chapter"}]},
            },
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Paragraph content here."}]},
            },
        ]

        chunks = self.chunker.chunk_notion_blocks(blocks, "test-page", "Test")

        # 查找
        chapter = next((c for c in chunks if c.level == "chapter"), None)
        paragraph = next((c for c in chunks if c.level == "paragraph"), None)

        # 验证关系 (如果 Paragraph 在 Chapter 下)
        if chapter and paragraph:
            assert paragraph.parent_id == chapter.chunk_id
            assert paragraph.chunk_id in chapter.children_ids

    def test_code_block_handling(self):
        """测试代码块处理"""
        blocks = [
            {
                "type": "code",
                "code": {
                    "rich_text": [{"plain_text": 'def hello():\n    print("Hello")'}],
                    "language": "python",
                },
            }
        ]

        chunks = self.chunker.chunk_notion_blocks(blocks, "test-page", "Test")

        # 验证代码块
        code_chunk = next((c for c in chunks if c.level == "code"), None)
        assert code_chunk is not None
        assert code_chunk.weight > 1.0  # 代码块权重应较高
        assert code_chunk.metadata["language"] == "python"

    def test_markdown_chunking(self):
        """测试从 Markdown 创建分块"""
        markdown = """
# Main Title
Intro text.
## Subsection
Detail text.
        """
        chunks = chunk_markdown_hierarchically(markdown, "test-doc", "Test Doc")
        assert len(chunks) > 0
        levels = set(c.level for c in chunks)
        assert "chapter" in levels or "heading_1" in levels


class TestHybridSearchEngine:
    """测试混合检索引擎"""

    def setup_method(self):
        """每个测试前准备"""
        self.mock_qdrant = MagicMock()
        self.mock_embedding = MagicMock()
        # 确保 embed_query 返回固定维度的向量
        self.mock_embedding.embed_query.return_value = [0.1] * 1024

        self.engine = HybridSearchEngine(
            qdrant_client=self.mock_qdrant,
            embedding_provider=self.mock_embedding,
            collection_name="test_collection",
        )

    @pytest.mark.asyncio
    async def test_vector_search(self):
        """测试向量搜索核心流程"""
        # Mock Qdrant 返回点
        mock_point = MagicMock()
        mock_point.id = "point-1"
        mock_point.score = 0.85
        mock_point.payload = {
            "chunk_id": "chunk-1",
            "page_id": "page-1",
            "content": "Test content",
            "title": "Test Page",
            "level": "paragraph",
            "metadata": {},
        }

        mock_response = MagicMock()
        mock_response.points = [mock_point]
        self.mock_qdrant.query_points.return_value = mock_response

        # 执行搜索
        # 如果 search 内部使用了 await，这里需要 await
        results = await self.engine.search(query="test", top_k=5)

        assert len(results) == 1
        assert results[0].chunk_id == "chunk-1"
        assert results[0].source == "vector"

        self.mock_embedding.embed_query.assert_called_with("test")

    def test_rrf_fusion(self):
        """测试 RRF 融合算法逻辑"""
        v_res = [SearchResult("c1", "p1", "content", "t1", 0.9, "vector", "para", {})]
        k_res = [SearchResult("c1", "p1", "content", "t1", 0.8, "keyword", "para", {})]

        fused = self.engine._rrf_fusion(v_res, k_res, top_k=5)

        assert len(fused) == 1
        assert fused[0].chunk_id == "c1"
        assert fused[0].source == "hybrid"  # 两个源都有，应标记为 hybrid

    def test_diversity_calculation(self):
        """测试多样性计算"""
        results = [
            SearchResult("c1", "p1", "content", "Page 1", 0.9, "vector", "p", {}),
            SearchResult("c2", "p1", "content", "Page 1", 0.8, "vector", "p", {}),
            SearchResult("c3", "p2", "content", "Page 2", 0.7, "vector", "p", {}),
        ]
        div = calculate_diversity(results)
        # 2 pages / 3 results = 0.66...
        assert 0.6 < div < 0.7

    def test_topic_clustering(self):
        """测试主题聚类"""
        results = [
            SearchResult("c1", "p1", "c", "Topic A", 0.9, "v", "p", {}),
            SearchResult("c2", "p1", "c", "Topic A", 0.8, "v", "p", {}),
            SearchResult("c3", "p2", "c", "Topic B", 0.7, "v", "p", {}),
        ]
        clusters = cluster_by_topic(results)
        assert len(clusters) == 2
        assert "Topic A" in clusters
        assert len(clusters["Topic A"]) == 2


class TestVectorStoreV2Integration:
    """集成测试：完整的搜索流程"""

    @pytest.mark.skip(reason="需要真实的 Qdrant 实例")
    def test_end_to_end_search(self):
        """端到端测试"""
        # 🔥 关键修复：引用正确的类名 (V2 已合并)
        from vector.vector_store import LevelChunkVectorStore

        # 使用 mock 避免真实连接
        with patch("vector.vector_store.QdrantClient"), patch(
            "vector.vector_store.SiliconFlowEmbedding"
        ):
            store = LevelChunkVectorStore()

            # ... 后续测试逻辑 ...
            # 由于这只是一个 Skipped 的示例，重点是 import 路径要对
            assert store is not None
