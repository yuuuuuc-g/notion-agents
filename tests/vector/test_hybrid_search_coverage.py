"""
tests/vector/test_hybrid_search_coverage.py
混合检索引擎覆盖率测试 - 精简版
"""
from unittest.mock import MagicMock, Mock, patch

import pytest

from vector.hybrid_search import (
    HybridSearchEngine,
    SearchResult,
    calculate_diversity,
    cluster_by_topic,
)


@pytest.fixture
def engine():
    """创建测试用的 HybridSearchEngine 实例"""
    mock_qdrant = MagicMock()
    mock_embedding = MagicMock()
    mock_embedding.embed_query.return_value = [0.1] * 1024

    engine = HybridSearchEngine(
        qdrant_client=mock_qdrant,
        embedding_provider=mock_embedding,
        collection_name="test_collection",
    )
    return engine


# ============================================================================
# 内存管理测试
# ============================================================================


def test_check_memory_usage_with_psutil(engine):
    """测试内存检查（有 psutil）"""
    with patch("vector.hybrid_search.PSUTIL_AVAILABLE", True):
        with patch("vector.hybrid_search.psutil") as mock_psutil:
            mock_process = MagicMock()
            mock_process.memory_info.return_value = Mock(rss=1024 * 1024 * 100)
            mock_psutil.Process.return_value = mock_process

            memory_mb = engine._check_memory_usage()
            assert memory_mb == 100.0


def test_check_memory_usage_without_psutil(engine):
    """测试内存检查（无 psutil）"""
    with patch("vector.hybrid_search.PSUTIL_AVAILABLE", False):
        memory_mb = engine._check_memory_usage()
        assert memory_mb == 0.0


def test_check_memory_usage_exception(engine):
    """测试内存检查异常处理"""
    with patch("vector.hybrid_search.PSUTIL_AVAILABLE", True):
        with patch("vector.hybrid_search.psutil") as mock_psutil:
            mock_psutil.Process.side_effect = Exception("Process not found")
            memory_mb = engine._check_memory_usage()
            assert memory_mb == 0.0


def test_should_load_reranker_disabled_by_config(engine):
    """测试配置禁用时不应加载重排序模型"""
    with patch("vector.hybrid_search.CONFIG_AVAILABLE", True):
        with patch("vector.hybrid_search.SETTINGS") as mock_settings:
            mock_settings.ENABLE_RERANKER = False
            assert engine._should_load_reranker() is False


def test_unload_reranker(engine):
    """测试卸载重排序模型"""
    engine._reranker = MagicMock()
    engine._reranker_loaded = True

    engine.unload_reranker()
    assert engine._reranker is None
    assert engine._reranker_loaded is False


def test_unload_reranker_not_loaded(engine):
    """测试卸载未加载的模型（无错误）"""
    engine._reranker = None
    engine._reranker_loaded = False

    engine.unload_reranker()  # 不应抛出异常
    assert engine._reranker is None


# ============================================================================
# 重排序模型测试
# ============================================================================


def test_get_reranker_model_name_from_settings(engine):
    """测试从配置获取模型名称"""
    with patch("vector.hybrid_search.CONFIG_AVAILABLE", True):
        with patch("vector.hybrid_search.SETTINGS") as mock_settings:
            mock_settings.RERANKER_MODEL_NAME = "custom-model"
            assert engine._get_reranker_model_name() == "custom-model"


def test_get_reranker_model_name_default(engine):
    """测试默认模型名称"""
    with patch("vector.hybrid_search.CONFIG_AVAILABLE", False):
        assert engine._get_reranker_model_name() == "BAAI/bge-reranker-large"


def test_estimate_reranker_size_from_mapping(engine):
    """测试从映射估算模型大小"""
    with patch.object(
        engine, "_get_reranker_model_name", return_value="BAAI/bge-reranker-base"
    ):
        size_mb = engine._estimate_reranker_size_mb()
        assert size_mb == 300.0


def test_estimate_reranker_size_default(engine):
    """测试默认模型大小估算"""
    with patch.object(engine, "_get_reranker_model_name", return_value="unknown-model"):
        size_mb = engine._estimate_reranker_size_mb()
        assert size_mb == 600.0


def test_get_reranker_stats(engine):
    """测试获取重排序模型统计"""
    engine._reranker_loaded = True
    engine._reranker_load_count = 5
    engine._reranker_last_used = 12345.0
    engine._memory_warning_shown = True

    stats = engine.get_reranker_stats()

    assert stats["loaded"] is True
    assert stats["load_count"] == 5
    assert stats["last_used"] == 12345.0
    assert stats["memory_warning_shown"] is True


def test_reranker_property_not_should_load(engine):
    """测试不应加载时 reranker 返回 None"""
    with patch.object(engine, "_should_load_reranker", return_value=False):
        assert engine.reranker is None


def test_reranker_property_already_loaded(engine):
    """测试已加载时直接返回"""
    mock_reranker = MagicMock()
    engine._reranker = mock_reranker
    engine._reranker_loaded = True

    with patch.object(engine, "_should_load_reranker", return_value=True):
        assert engine.reranker == mock_reranker


# ============================================================================
# 搜索测试
# ============================================================================


@pytest.mark.asyncio
async def test_search_vector_search_exception(engine):
    """测试向量搜索异常处理"""
    engine.qdrant.query_points.side_effect = Exception("Qdrant Error")

    results = await engine.search(query="test", top_k=5)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_with_keyword_search_failure(engine):
    """测试关键词搜索失败时的容错"""
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
    engine.qdrant.query_points.return_value = mock_response

    # 模拟关键词搜索失败
    engine.notion = MagicMock()
    engine.notion.search = MagicMock(side_effect=Exception("API Error"))

    results = await engine.search(query="test", top_k=5)

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"


# ============================================================================
# RRF 融合测试
# ============================================================================


def test_rrf_fusion_empty_results(engine):
    """测试空结果融合"""
    fused = engine._rrf_fusion([], [], top_k=5)
    assert len(fused) == 0


def test_rrf_fusion_vector_only(engine):
    """测试仅向量结果融合"""
    v_res = [
        SearchResult("c1", "p1", "content1", "t1", 0.9, "vector", "para", {}),
        SearchResult("c2", "p2", "content2", "t2", 0.8, "vector", "para", {}),
    ]

    fused = engine._rrf_fusion(v_res, [], top_k=5)

    assert len(fused) == 2
    assert fused[0].chunk_id == "c1"
    assert fused[0].source == "vector"


def test_rrf_fusion_keyword_only(engine):
    """测试仅关键词结果融合"""
    k_res = [
        SearchResult("c1", "p1", "content1", "t1", 0.9, "keyword", "para", {}),
        SearchResult("c2", "p2", "content2", "t2", 0.8, "keyword", "para", {}),
    ]

    fused = engine._rrf_fusion([], k_res, top_k=5)

    assert len(fused) == 2
    assert fused[0].chunk_id == "c1"
    assert fused[0].source == "keyword"


def test_rrf_fusion_score_update(engine):
    """测试融合后分数更新"""
    v_res = [SearchResult("c1", "p1", "content", "t1", 0.9, "vector", "para", {})]
    k_res = [SearchResult("c1", "p1", "content", "t1", 0.8, "keyword", "para", {})]

    fused = engine._rrf_fusion(v_res, k_res, top_k=5)

    assert len(fused) == 1
    assert fused[0].source == "hybrid"


# ============================================================================
# 重排序测试
# ============================================================================


@pytest.mark.asyncio
async def test_rerank_no_reranker(engine):
    """测试无重排序模型时直接返回"""
    with patch.object(engine, "reranker", None):
        candidates = [
            SearchResult("c1", "p1", "content", "t1", 0.9, "vector", "para", {})
        ]
        results = await engine._rerank("query", candidates)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_rerank_success(engine):
    """测试重排序成功"""
    mock_reranker = MagicMock()
    mock_reranker.predict.return_value = [0.9, 0.7]

    with patch.object(engine, "reranker", mock_reranker):
        candidates = [
            SearchResult("c1", "p1", "content1", "t1", 0.5, "vector", "para", {}),
            SearchResult("c2", "p2", "content2", "t2", 0.8, "vector", "para", {}),
        ]
        results = await engine._rerank("query", candidates)

        assert len(results) == 2
        assert results[0].score == 0.9
        assert "reranked" in results[0].source


@pytest.mark.asyncio
async def test_rerank_exception(engine):
    """测试重排序异常处理"""
    mock_reranker = MagicMock()
    mock_reranker.predict.side_effect = Exception("Rerank Error")

    with patch.object(engine, "reranker", mock_reranker):
        candidates = [
            SearchResult("c1", "p1", "content", "t1", 0.9, "vector", "para", {})
        ]
        results = await engine._rerank("query", candidates)

        assert len(results) == 1
        assert results[0].chunk_id == "c1"


# ============================================================================
# search_with_context 测试
# ============================================================================


def test_search_with_context_no_chunk_map(engine):
    """测试无 chunk_map 时的处理"""
    results = [SearchResult("c1", "p1", "content", "t1", 0.9, "vector", "para", {})]
    results_with_context = engine.search_with_context(results, {})

    assert len(results_with_context) == 1
    assert results_with_context[0]["chunk_id"] == "c1"


def test_search_with_context_with_parent(engine):
    """测试有父块的上下文"""
    from vector.hierarchical_chunker import HierarchicalChunk

    results = [
        SearchResult("c2", "p1", "Paragraph", "t1", 0.9, "vector", "paragraph", {})
    ]

    chunk_map = {
        "c1": HierarchicalChunk(
            chunk_id="c1",
            content="Chapter Title",
            level="chapter",
            weight=2.0,
            parent_id=None,
            children_ids=["c2"],
            block_type="heading_1",
            metadata={},
        ),
        "c2": HierarchicalChunk(
            chunk_id="c2",
            content="Paragraph",
            level="paragraph",
            weight=1.0,
            parent_id="c1",
            children_ids=[],
            block_type="paragraph",
            metadata={},
        ),
    }

    results_with_context = engine.search_with_context(results, chunk_map)

    assert len(results_with_context) == 1
    assert results_with_context[0]["has_parent"] is True


# ============================================================================
# auto_unload_idle_models 测试
# ============================================================================


def test_auto_unload_idle_models_not_loaded(engine):
    """测试未加载模型时不卸载"""
    engine._reranker_loaded = False
    result = engine.auto_unload_idle_models(idle_threshold_seconds=300)
    assert result is False


def test_auto_unload_idle_models_not_idle(engine):
    """测试未闲置时不卸载"""
    import time

    engine._reranker_loaded = True
    engine._reranker = MagicMock()
    engine._reranker_last_used = time.time()

    result = engine.auto_unload_idle_models(idle_threshold_seconds=300)
    assert result is False


def test_auto_unload_idle_models_success(engine):
    """测试成功卸载闲置模型"""
    import time

    engine._reranker_loaded = True
    engine._reranker = MagicMock()
    engine._reranker_last_used = time.time() - 600

    result = engine.auto_unload_idle_models(idle_threshold_seconds=300)
    assert result is True
    assert engine._reranker is None
    assert engine._reranker_loaded is False


# ============================================================================
# 辅助函数测试
# ============================================================================


def test_calculate_diversity_empty():
    """测试空结果的多样性"""
    div = calculate_diversity([])
    assert div == 0.0


def test_calculate_diversity_dict_input():
    """测试字典类型输入的多样性"""
    results = [
        {"page_id": "p1", "title": "Page 1"},
        {"page_id": "p1", "title": "Page 1"},
        {"page_id": "p2", "title": "Page 2"},
    ]
    div = calculate_diversity(results)
    assert div == 2 / 3


def test_cluster_by_topic_empty():
    """测试空结果的主题聚类"""
    clusters = cluster_by_topic([])
    assert clusters == {}


def test_cluster_by_topic_dict_input():
    """测试字典类型输入的主题聚类"""
    results = [
        {"title": "Topic A"},
        {"title": "Topic A"},
        {"title": "Topic B"},
    ]
    clusters = cluster_by_topic(results, top_n_topics=5)
    assert len(clusters) == 2
    assert len(clusters["Topic A"]) == 2
    assert len(clusters["Topic B"]) == 1


def test_cluster_by_topic_no_title():
    """测试无标题时的处理"""
    results = [{"page_id": "p1"}]
    clusters = cluster_by_topic(results)
    assert "Untitled" in clusters


# ============================================================================
# SearchResult 测试
# ============================================================================


def test_search_result_to_dict():
    """测试 SearchResult 转换为字典"""
    result = SearchResult(
        chunk_id="c1",
        page_id="p1",
        content="content",
        title="title",
        score=0.9,
        source="vector",
        level="paragraph",
        metadata={"key": "value"},
    )

    d = result.to_dict()

    assert d["chunk_id"] == "c1"
    assert d["page_id"] == "p1"
    assert d["content"] == "content"
    assert d["title"] == "title"
    assert d["score"] == 0.9
    assert d["source"] == "vector"
    assert d["level"] == "paragraph"
    assert d["metadata"] == {"key": "value"}


# ============================================================================
# 向量搜索测试
# ============================================================================


@pytest.mark.asyncio
async def test_vector_search_with_domain_filter(engine):
    """测试带 domain 过滤的向量搜索"""
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
    engine.qdrant.query_points.return_value = mock_response

    results = await engine._vector_search(
        query="test",
        top_k=5,
        domain="Tech",
        level_filter=None,
        min_score=0.5,
    )

    assert len(results) == 1


@pytest.mark.asyncio
async def test_vector_search_no_filters(engine):
    """测试无过滤条件的向量搜索"""
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
    engine.qdrant.query_points.return_value = mock_response

    results = await engine._vector_search(
        query="test",
        top_k=5,
        domain="All",
        level_filter=None,
        min_score=0.5,
    )

    assert len(results) == 1


@pytest.mark.asyncio
async def test_vector_search_exception(engine):
    """测试向量搜索异常"""
    engine.qdrant.query_points.side_effect = Exception("Qdrant Error")

    results = await engine._vector_search(
        query="test",
        top_k=5,
        domain=None,
        level_filter=None,
        min_score=0.5,
    )

    assert len(results) == 0


# ============================================================================
# 关键词搜索测试
# ============================================================================


@pytest.mark.asyncio
async def test_keyword_search_no_notion_service(engine):
    """测试无 Notion 服务时的关键词搜索"""
    engine.notion = None
    results = await engine._keyword_search("test", 5, None)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_keyword_search_exception(engine):
    """测试关键词搜索异常"""
    engine.notion = MagicMock()
    engine.notion.search = MagicMock(side_effect=Exception("API Error"))

    results = await engine._keyword_search("test", 5, None)
    assert len(results) == 0
