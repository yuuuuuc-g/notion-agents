"""
vector/hybrid_search.py
混合检索引擎 - 向量搜索 + 关键词搜索 + RRF 融合排序

核心改进：
1. 向量搜索（Qdrant）：语义相似度匹配
2. 关键词搜索（Notion API）：精准关键词匹配
3. RRF 融合排序：结合两种搜索的优势
4. 重排序（可选）：使用 Cross-Encoder 提升精度
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.http import models

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """搜索结果数据结构"""

    chunk_id: str  # 分块 ID
    page_id: str  # 页面 ID
    content: str  # 文本内容
    title: str  # 页面标题
    score: float  # 相似度分数
    source: str  # 来源：vector/keyword/hybrid
    level: str  # 层级：chapter/section/paragraph
    metadata: Dict  # 额外元数据

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "chunk_id": self.chunk_id,
            "page_id": self.page_id,
            "content": self.content,
            "title": self.title,
            "score": self.score,
            "source": self.source,
            "level": self.level,
            "metadata": self.metadata,
        }


class HybridSearchEngine:
    """
    混合检索引擎

    使用场景：
    1. 用户搜索："Python 列表推导式"
       - 向量搜索：找到语义相关的内容
       - 关键词搜索：精准匹配 "Python" 和 "列表推导式"
       - RRF 融合：综合两种结果

    2. 技术文档搜索：关键词权重高
    3. 日常笔记搜索：语义权重高
    """

    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedding_provider,
        notion_service=None,  # 可选，用于关键词搜索
        collection_name: str = "biobrain_memory",
    ):
        self.qdrant = qdrant_client
        self.embedding = embedding_provider
        self.notion = notion_service
        self.collection_name = collection_name

        # RRF 参数
        self.rrf_k = 60  # RRF 常数（论文推荐值）

        # 搜索权重
        self.vector_weight = 0.6  # 向量搜索权重
        self.keyword_weight = 0.4  # 关键词搜索权重

    async def search(
        self,
        query: str,
        top_k: int = 10,
        domain: Optional[str] = None,
        level_filter: Optional[List[str]] = None,  # ['chapter', 'section', 'paragraph']
        use_reranker: bool = False,
        min_score: float = 0.45,  # 降低阈值，提高召回率
    ) -> List[SearchResult]:
        """
        混合搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            domain: 领域过滤（如 "Spanish", "Tech"）
            level_filter: 层级过滤（如只搜索标题）
            use_reranker: 是否使用重排序模型
            min_score: 最低分数阈值

        Returns:
            搜索结果列表
        """
        logger.info(f"🔍 [HybridSearch] Query: '{query}' (top_k={top_k})")

        # 1. 向量搜索
        vector_results = await self._vector_search(
            query=query,
            top_k=top_k * 2,  # 取 2 倍候选，用于融合
            domain=domain,
            level_filter=level_filter,
            min_score=min_score,
        )

        # 2. 关键词搜索（如果有 Notion Service）
        keyword_results = []
        if self.notion:
            try:
                keyword_results = await self._keyword_search(
                    query=query, top_k=top_k * 2, domain=domain
                )
            except Exception as e:
                logger.warning(f"⚠️ Keyword search failed: {e}")

        # 3. RRF 融合排序
        fused_results = self._rrf_fusion(
            vector_results=vector_results,
            keyword_results=keyword_results,
            top_k=top_k * 2,
        )

        # 4. 重排序（可选）
        if use_reranker and len(fused_results) > 1:
            try:
                fused_results = await self._rerank(query, fused_results)
            except Exception as e:
                logger.warning(f"⚠️ Reranking failed: {e}")

        # 5. 返回 Top-K
        final_results = fused_results[:top_k]

        logger.info(
            f"✅ [HybridSearch] Found {len(final_results)} results "
            f"(vector: {len(vector_results)}, keyword: {len(keyword_results)})"
        )

        return final_results

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        domain: Optional[str],
        level_filter: Optional[List[str]],
        min_score: float,
    ) -> List[SearchResult]:
        """向量搜索"""
        try:
            # 生成查询向量
            query_vector = self.embedding.embed_query(query)

            # 构建过滤条件
            filter_conditions = []

            if domain and domain != "All":
                filter_conditions.append(
                    models.FieldCondition(
                        key="domain", match=models.MatchValue(value=domain)
                    )
                )

            if level_filter:
                filter_conditions.append(
                    models.FieldCondition(
                        key="level", match=models.MatchAny(any=level_filter)
                    )
                )

            # 执行搜索
            search_result = self.qdrant.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=min_score,
                query_filter=models.Filter(must=filter_conditions)
                if filter_conditions
                else None,
            )

            # 转换为 SearchResult
            results = []
            for point in search_result.points:
                payload = point.payload
                results.append(
                    SearchResult(
                        chunk_id=payload.get("chunk_id", str(point.id)),
                        page_id=payload.get("page_id", ""),
                        content=payload.get("content", ""),
                        title=payload.get("title", "Untitled"),
                        score=point.score,
                        source="vector",
                        level=payload.get("level", "paragraph"),
                        metadata=payload.get("metadata", {}),
                    )
                )

            logger.debug(
                f"📊 [VectorSearch] {len(results)} results (scores: {[r.score for r in results[:3]]})"
            )
            return results

        except Exception as e:
            logger.error(f"❌ Vector search failed: {e}")
            return []

    async def _keyword_search(
        self, query: str, top_k: int, domain: Optional[str]
    ) -> List[SearchResult]:
        """
        关键词搜索（通过 Notion API）

        注意：这是一个简化实现，真实场景需要调用 Notion 的 search API
        """
        try:
            # 调用 Notion API 搜索
            # notion_results = await self.notion.search(query=query, filter=...)

            # 这里暂时返回空列表，因为 Notion API 的搜索需要特殊配置
            # 实际使用时，可以通过 notion_service.client.search(...) 调用

            logger.debug("📊 [KeywordSearch] Skipped (Notion API search not configured)")
            return []

        except Exception as e:
            logger.error(f"❌ Keyword search failed: {e}")
            return []

    def _rrf_fusion(
        self,
        vector_results: List[SearchResult],
        keyword_results: List[SearchResult],
        top_k: int,
    ) -> List[SearchResult]:
        """
        RRF (Reciprocal Rank Fusion) 融合排序

        公式: RRF_score = Σ 1 / (k + rank_i)

        Args:
            vector_results: 向量搜索结果
            keyword_results: 关键词搜索结果
            top_k: 返回数量

        Returns:
            融合后的结果
        """
        # 使用 chunk_id 作为唯一标识
        fused_scores: Dict[str, Tuple[SearchResult, float]] = {}

        # 1. 向量搜索结果的 RRF 分数
        for rank, result in enumerate(vector_results):
            rrf_score = self.vector_weight / (self.rrf_k + rank + 1)

            if result.chunk_id in fused_scores:
                # 已存在，累加分数
                existing_result, existing_score = fused_scores[result.chunk_id]
                fused_scores[result.chunk_id] = (
                    existing_result,
                    existing_score + rrf_score,
                )
            else:
                fused_scores[result.chunk_id] = (result, rrf_score)

        # 2. 关键词搜索结果的 RRF 分数
        for rank, result in enumerate(keyword_results):
            rrf_score = self.keyword_weight / (self.rrf_k + rank + 1)

            if result.chunk_id in fused_scores:
                existing_result, existing_score = fused_scores[result.chunk_id]
                fused_scores[result.chunk_id] = (
                    existing_result,
                    existing_score + rrf_score,
                )
            else:
                # 标记为来自关键词搜索
                result.source = "keyword"
                fused_scores[result.chunk_id] = (result, rrf_score)

        # 3. 按融合分数排序
        sorted_results = sorted(fused_scores.values(), key=lambda x: x[1], reverse=True)

        # 4. 更新分数和来源
        final_results = []
        for result, fused_score in sorted_results[:top_k]:
            # 如果同时出现在两个结果中，标记为 hybrid
            if result.source == "vector" and any(
                kr.chunk_id == result.chunk_id for kr in keyword_results
            ):
                result.source = "hybrid"

            # 更新为融合分数
            result.score = fused_score
            final_results.append(result)

        return final_results

    async def _rerank(
        self, query: str, candidates: List[SearchResult]
    ) -> List[SearchResult]:
        """
        使用 Cross-Encoder 重排序

        需要安装: pip install sentence-transformers
        """
        try:
            from sentence_transformers import CrossEncoder

            # 加载重排序模型（首次会下载，约 400MB）
            reranker = CrossEncoder("BAAI/bge-reranker-large")

            # 准备输入对
            pairs = [(query, result.content) for result in candidates]

            # 计算重排序分数
            rerank_scores = reranker.predict(pairs)

            # 按重排序分数排序
            reranked = sorted(
                zip(candidates, rerank_scores), key=lambda x: x[1], reverse=True
            )

            # 更新分数
            results = []
            for result, score in reranked:
                result.score = float(score)
                result.source = f"{result.source}_reranked"
                results.append(result)

            logger.debug(f"♻️ [Reranker] Reranked {len(results)} results")
            return results

        except ImportError:
            logger.warning("⚠️ sentence-transformers not installed, skipping reranking")
            return candidates
        except Exception as e:
            logger.error(f"❌ Reranking failed: {e}")
            return candidates

    def search_with_context(
        self,
        results: List[SearchResult],
        chunk_map: Dict[str, any],  # chunk_id -> HierarchicalChunk
    ) -> List[Dict]:
        """
        为搜索结果添加上下文信息

        Args:
            results: 搜索结果
            chunk_map: chunk_id 到 HierarchicalChunk 的映射

        Returns:
            带上下文的搜索结果
        """
        results_with_context = []

        for result in results:
            chunk = chunk_map.get(result.chunk_id)
            if not chunk:
                results_with_context.append(result.to_dict())
                continue

            # 获取父块（章节/小节）
            parent_text = ""
            if chunk.parent_id and chunk.parent_id in chunk_map:
                parent = chunk_map[chunk.parent_id]
                parent_text = f"[{parent.level.upper()}] {parent.content}\n\n"

            # 获取子块（如果当前是章节/小节）
            children_text = ""
            if chunk.children_ids:
                children = [
                    chunk_map[cid] for cid in chunk.children_ids if cid in chunk_map
                ]
                if children:
                    children_text = "\n" + "\n".join(
                        [f"  - {child.content}" for child in children[:3]]
                    )
                    if len(children) > 3:
                        children_text += f"\n  ... ({len(children) - 3} more)"

            # 组合完整上下文
            full_context = f"{parent_text}{result.content}{children_text}"

            result_dict = result.to_dict()
            result_dict["full_context"] = full_context
            result_dict["has_parent"] = bool(chunk.parent_id)
            result_dict["children_count"] = len(chunk.children_ids)

            results_with_context.append(result_dict)

        return results_with_context


# 辅助函数：计算搜索结果的多样性
def calculate_diversity(results: List[SearchResult]) -> float:
    """
    计算搜索结果的多样性

    多样性 = 不同页面数 / 总结果数

    用于判断是否需要向用户澄清（主题分散）
    """
    if not results:
        return 0.0

    unique_pages = len(set(r.page_id for r in results))
    diversity = unique_pages / len(results)

    return diversity


# 辅助函数：主题聚类
def cluster_by_topic(
    results: List[SearchResult], top_n_topics: int = 5
) -> Dict[str, List[SearchResult]]:
    """
    按主题聚类搜索结果

    简化版：按页面标题聚类
    高级版：可使用 LLM 提取主题标签
    """
    clusters: Dict[str, List[SearchResult]] = {}

    for result in results:
        # 使用页面标题作为主题
        topic = result.title

        if topic not in clusters:
            clusters[topic] = []
        clusters[topic].append(result)

    # 按簇大小排序，取前 N 个
    sorted_clusters = dict(
        sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)[:top_n_topics]
    )

    return sorted_clusters


if __name__ == "__main__":
    # 测试代码
    from qdrant_client import QdrantClient

    from vector.embedding_provider import SiliconFlowEmbedding

    # 初始化
    client = QdrantClient(":memory:")
    embedding = SiliconFlowEmbedding()

    search_engine = HybridSearchEngine(
        qdrant_client=client, embedding_provider=embedding
    )

    # 测试搜索
    # results = asyncio.run(search_engine.search("Python 列表推导式"))
    # for result in results:
    #     print(f"[{result.source}] {result.title}: {result.content[:100]}... (score: {result.score:.3f})")
