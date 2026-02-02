"""
vector/hybrid_search.py
混合检索引擎 - 向量搜索 + 关键词搜索 + RRF 融合排序

核心改进：
1. 向量搜索（Qdrant）：语义相似度匹配
2. 关键词搜索（Notion API）：精准关键词匹配
3. RRF 融合排序：结合两种搜索的优势
4. 重排序（可选）：使用 Cross-Encoder 提升精度
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from qdrant_client import QdrantClient
from qdrant_client.http import models

# 导入配置
try:
    from config.settings import SETTINGS

    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    SETTINGS = None

# 导入内存监控
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

from utils.logger import get_logger

# 默认重排序模型
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-large"

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """搜索结果数据结构"""

    chunk_id: str
    page_id: str
    content: str
    title: str
    score: float
    source: str
    level: str
    metadata: Dict

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

        # 重排序模型缓存和内存优化字段
        self._reranker = None
        self._reranker_loaded = False
        self._reranker_last_used = 0.0  # 上次使用时间戳
        self._reranker_load_count = 0  # 加载次数统计
        self._memory_warning_shown = False  # 内存警告是否已显示

    def _check_memory_usage(self) -> float:
        """
        检查当前进程内存使用情况
        返回：内存使用量（MB）
        """
        if not PSUTIL_AVAILABLE:
            return 0.0

        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # 转换为MB
            return memory_mb
        except Exception as e:
            logger.warning(f"⚠️ Memory check failed: {e}")
            return 0.0

    def _should_load_reranker(self) -> bool:
        """
        判断是否应该加载重排序模型
        考虑因素：配置、内存使用、上次使用时间
        """
        # 1. 检查配置是否启用
        if CONFIG_AVAILABLE and SETTINGS and hasattr(SETTINGS, "ENABLE_RERANKER"):
            if not SETTINGS.ENABLE_RERANKER:
                logger.debug("📉 Reranker disabled by configuration")
                return False

        # 2. 检查内存使用情况
        if PSUTIL_AVAILABLE and CONFIG_AVAILABLE and SETTINGS:
            memory_mb = self._check_memory_usage()
            max_memory = getattr(SETTINGS, "MAX_MEMORY_MB", 2048)

            if memory_mb > max_memory * 0.8:  # 超过80%内存限制
                if not self._memory_warning_shown:
                    logger.warning(
                        f"⚠️ High memory usage ({memory_mb:.1f}MB > {max_memory * 0.8:.0f}MB), "
                        "consider disabling reranker"
                    )
                    self._memory_warning_shown = True
                return False

        # 3. 如果模型已经加载，直接返回
        if self._reranker_loaded and self._reranker is not None:
            self._reranker_last_used = time.time()
            return True

        return True

    def unload_reranker(self):
        """
        卸载重排序模型以释放内存
        """
        if self._reranker is not None:
            logger.info("🗑️ Unloading reranker model to free memory")
            self._reranker = None
            self._reranker_loaded = False

    def _get_reranker_model_name(self) -> str:
        """
        获取当前配置的重排序模型名称
        """
        if CONFIG_AVAILABLE and SETTINGS and hasattr(SETTINGS, "RERANKER_MODEL_NAME"):
            return SETTINGS.RERANKER_MODEL_NAME
        return DEFAULT_RERANKER_MODEL

    def _estimate_reranker_size_mb(self) -> float:
        """
        估算重排序模型内存占用（MB）

        策略：
        1. 如果模型已加载，尝试使用PyTorch API获取实际内存占用
        2. 否则，根据模型名称映射到已知的近似内存大小
        3. 默认回退到保守估计（600MB）
        """
        # 已知模型名称到近似内存大小（MB）的映射
        MODEL_SIZE_MAPPING = {
            "BAAI/bge-reranker-large": 600.0,
            "BAAI/bge-reranker-base": 300.0,
            "cross-encoder/ms-marco-MiniLM-L-6-v2": 200.0,
            "default": 600.0,
        }

        model_name = self._get_reranker_model_name()

        # 如果模型已加载，尝试使用PyTorch测量实际内存占用
        if self._reranker_loaded and self._reranker is not None:
            try:
                import torch

                # CrossEncoder 模型通常有 .model 属性
                if hasattr(self._reranker, "model"):
                    model = self._reranker.model
                    # 估算参数内存占用
                    param_size = sum(
                        p.numel() * p.element_size() for p in model.parameters()
                    )
                    buffer_size = sum(
                        b.numel() * b.element_size() for b in model.buffers()
                    )
                    total_size_mb = (param_size + buffer_size) / (1024 * 1024)
                    return total_size_mb
                # 如果无法获取模型对象，使用CUDA内存分配（如果使用GPU）
                if torch.cuda.is_available():
                    cuda_mb = torch.cuda.memory_allocated() / (1024 * 1024)
                    if cuda_mb > 10:
                        return cuda_mb
            except ImportError:
                pass  # PyTorch不可用，回退到映射估计

        # 使用模型名称映射估计
        for key, size_mb in MODEL_SIZE_MAPPING.items():
            if key in model_name:
                return size_mb

        return MODEL_SIZE_MAPPING["default"]

    def get_reranker_stats(self) -> Dict[str, Any]:
        """
        获取重排序模型统计信息
        """
        model_size_mb = 0.0
        try:
            model_size_mb = self._estimate_reranker_size_mb()
        except Exception as e:
            logger.warning(f"⚠️ Failed to estimate reranker model size: {e}")
            model_size_mb = 600.0  # 默认保守估计

        return {
            "loaded": self._reranker_loaded,
            "load_count": self._reranker_load_count,
            "last_used": self._reranker_last_used,
            "memory_warning_shown": self._memory_warning_shown,
            "model_size_mb": round(model_size_mb, 2),
        }

    @property
    def reranker(self):
        """
        懒加载 CrossEncoder 重排序模型（内存优化版）
        添加了配置检查、内存监控和自动卸载机制
        """
        # 检查是否应该加载重排序模型
        if not self._should_load_reranker():
            return None

        # 如果模型已经加载，更新使用时间并返回
        if self._reranker_loaded and self._reranker is not None:
            self._reranker_last_used = time.time()
            return self._reranker

        # 加载重排序模型
        if self._reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                # 从配置获取模型名称，默认为 large 版本
                model_name = DEFAULT_RERANKER_MODEL
                if (
                    CONFIG_AVAILABLE
                    and SETTINGS
                    and hasattr(SETTINGS, "RERANKER_MODEL_NAME")
                ):
                    model_name = SETTINGS.RERANKER_MODEL_NAME

                logger.info(f"⏳ Loading CrossEncoder model '{model_name}'...")
                self._reranker = CrossEncoder(model_name)
                self._reranker_loaded = True
                self._reranker_load_count += 1
                self._reranker_last_used = time.time()
                logger.info(
                    f"✅ CrossEncoder loaded successfully. (Load count: {self._reranker_load_count})"
                )
            except ImportError:
                logger.warning(
                    "⚠️ sentence-transformers not installed, skipping reranking"
                )
                self._reranker = None
            except Exception as e:
                logger.error(f"❌ Failed to load CrossEncoder: {e}")
                self._reranker = None

        return self._reranker

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
        # 检查配置是否允许使用重排序
        should_rerank = use_reranker
        if CONFIG_AVAILABLE and SETTINGS and hasattr(SETTINGS, "ENABLE_RERANKER"):
            if not SETTINGS.ENABLE_RERANKER:
                logger.debug("📉 Reranker disabled by configuration, skipping")
                should_rerank = False

        if should_rerank and len(fused_results) > 1:
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
        """
        try:
            # 调用 Notion API 搜索 (占位实现)
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
        """
        # 使用 chunk_id 作为唯一标识
        fused_scores: Dict[str, Tuple[SearchResult, float]] = {}

        # 1. 向量搜索结果的 RRF 分数
        for rank, result in enumerate(vector_results):
            rrf_score = self.vector_weight / (self.rrf_k + rank + 1)

            if result.chunk_id in fused_scores:
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
                result.source = "keyword"
                fused_scores[result.chunk_id] = (result, rrf_score)

        # 3. 按融合分数排序
        sorted_results = sorted(fused_scores.values(), key=lambda x: x[1], reverse=True)

        # 4. 更新分数和来源
        final_results = []
        for result, fused_score in sorted_results[:top_k]:
            if result.source == "vector" and any(
                kr.chunk_id == result.chunk_id for kr in keyword_results
            ):
                result.source = "hybrid"

            result.score = fused_score
            final_results.append(result)

        return final_results

    async def _rerank(
        self, query: str, candidates: List[SearchResult]
    ) -> List[SearchResult]:
        """
        使用 Cross-Encoder 重排序
        """
        reranker = self.reranker
        if reranker is None:
            logger.debug("⚠️ Reranker not available, skipping reranking")
            return candidates

        try:
            pairs = [(query, result.content) for result in candidates]
            rerank_scores = reranker.predict(pairs)

            reranked = sorted(
                zip(candidates, rerank_scores), key=lambda x: x[1], reverse=True
            )

            results = []
            for result, score in reranked:
                result.score = float(score)
                result.source = f"{result.source}_reranked"
                results.append(result)

            logger.debug(f"♻️ [Reranker] Reranked {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"❌ Reranking failed: {e}")
            return candidates

    def search_with_context(
        self,
        results: List[SearchResult],
        chunk_map: Dict[str, Any],  # chunk_id -> HierarchicalChunk
    ) -> List[Dict]:
        """
        为搜索结果添加上下文信息

        Week 6 Agent 强依赖此方法来获取结果并进行分析。
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

            # 获取子块
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

    def auto_unload_idle_models(self, idle_threshold_seconds: int = 300) -> bool:
        """
        自动卸载闲置的重排序模型以释放内存

        参数:
            idle_threshold_seconds: 闲置时间阈值（秒），默认5分钟

        返回:
            bool: 是否有模型被卸载
        """
        unloaded = False
        current_time = time.time()

        # 检查重排序模型
        if (
            self._reranker_loaded
            and self._reranker is not None
            and current_time - self._reranker_last_used > idle_threshold_seconds
        ):
            logger.info(
                f"🗑️ Auto-unloading reranker model (idle for "
                f"{int(current_time - self._reranker_last_used)}s)"
            )
            self.unload_reranker()
            unloaded = True

        return unloaded


# =============================================================================
# 🔥 辅助函数 (关键修复：兼容 Dict 和 SearchResult)
# =============================================================================


def calculate_diversity(results: List[Union[SearchResult, Dict]]) -> float:
    """
    计算搜索结果的多样性

    多样性 = 不同页面数 / 总结果数
    🔥 修复：兼容 SearchResult 对象和字典类型访问
    """
    if not results:
        return 0.0

    unique_pages = set()
    for r in results:
        # 兼容性判断：如果是字典用 get，如果是对象用 getattr
        if isinstance(r, dict):
            page_id = r.get("page_id")
        else:
            page_id = getattr(r, "page_id", None)

        if page_id:
            unique_pages.add(page_id)

    diversity = len(unique_pages) / len(results)
    return diversity


def cluster_by_topic(
    results: List[Union[SearchResult, Dict]], top_n_topics: int = 5
) -> Dict[str, List[Union[SearchResult, Dict]]]:
    """
    按主题聚类搜索结果

    🔥 修复：兼容 SearchResult 对象和字典类型访问
    """
    clusters: Dict[str, List[Any]] = {}

    for result in results:
        # 兼容性判断
        if isinstance(result, dict):
            topic = result.get("title", "Untitled")
        else:
            topic = getattr(result, "title", "Untitled")

        if not topic:
            topic = "Untitled"

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
