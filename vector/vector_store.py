"""
vector/vector_store.py
[Qdrant Hybrid Search Native Version]
版本：v5.1 (Fix FusionQuery Param)
修复：models.FusionQuery 参数名从 method 修正为 fusion
"""

import os
import threading
import time
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

# 导入配置
try:
    from config.settings import SETTINGS

    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    SETTINGS = None

from utils.logger import get_logger

from .doc_store import DOC_STORE
from .embedding_provider import SiliconFlowEmbedding
from .hierarchical_chunker import HierarchicalChunk, HierarchicalChunker
from .vector_interface import IVectorStore

# 导入配置和内存监控
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# 尝试导入稀疏向量模型
try:
    from fastembed import SparseTextEmbedding

    SPARSE_MODEL_AVAILABLE = True
except ImportError:
    SPARSE_MODEL_AVAILABLE = False

logger = get_logger(__name__)

# 类型提示导入（仅用于类型检查）
if TYPE_CHECKING:
    from fastembed import SparseTextEmbedding

# 默认稀疏模型
DEFAULT_SPARSE_MODEL = "prithivida/Splade_PP_en_v1"


class LevelChunkVectorStore(IVectorStore):
    """
    升级版向量存储 (Singleton + Hybrid)
    """

    _instance = None
    _initialized = False
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super(LevelChunkVectorStore, cls).__new__(cls)
        return cls._instance

    def __init__(self, collection_name: Optional[str] = None):
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            self.collection_name = collection_name or os.getenv(
                "QDRANT_COLLECTION", "biobrain_memory_hybrid"
            )
            self.host = os.getenv("QDRANT_HOST", "localhost")
            self.port = int(os.getenv("QDRANT_PORT", 6333))

            self._client: Optional[QdrantClient] = None
            self._embedding_provider: Optional[Any] = None
            self._sparse_embedding_model: Optional[Any] = None
            self._chunker: Optional[Any] = None
            self.chunk_cache: Dict[str, HierarchicalChunk] = {}

            # 内存优化相关字段
            self._sparse_model_loaded = False
            self._sparse_model_last_used = 0.0  # 上次使用时间戳
            self._sparse_model_load_count = 0  # 加载次数统计
            self._memory_warning_shown = False  # 内存警告是否已显示

            self._initialized = True
            logger.info("💤 [VectorStore] Initialized (Lazy Mode).")

            if not SPARSE_MODEL_AVAILABLE:
                logger.warning(
                    "⚠️ 'fastembed' not installed. Hybrid search (Sparse) will be disabled."
                )

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            with self._init_lock:
                if self._client is None:
                    self._connect()
        # self._connect() 应该已经设置了self._client
        assert self._client is not None, "Qdrant client not initialized"
        return self._client

    @property
    def embedding_provider(self):
        if self._embedding_provider is None:
            with self._init_lock:
                if self._embedding_provider is None:
                    self._embedding_provider = SiliconFlowEmbedding()
        return self._embedding_provider

    @property
    def sparse_model(self) -> Optional[Any]:
        """
        稀疏模型属性（内存优化版）
        添加了配置检查、内存监控和自动卸载机制
        """
        # 检查是否应该加载稀疏模型
        if not self._should_load_sparse_model():
            return None

        # 如果模型已经加载，更新使用时间并返回
        if self._sparse_model_loaded and self._sparse_embedding_model is not None:
            self._sparse_model_last_used = time.time()
            return self._sparse_embedding_model

        # 加载稀疏模型（线程安全）
        if self._sparse_embedding_model is None:
            with self._init_lock:
                if self._sparse_embedding_model is None:
                    # 再次检查配置（在锁内）
                    if not self._should_load_sparse_model():
                        return None

                    # 从配置获取模型名称，默认为轻量级模型
                    model_name = DEFAULT_SPARSE_MODEL
                    if (
                        CONFIG_AVAILABLE
                        and SETTINGS
                        and hasattr(SETTINGS, "SPARSE_MODEL_NAME")
                    ):
                        model_name = SETTINGS.SPARSE_MODEL_NAME

                    logger.info(f"⏳ Loading Sparse Model: {model_name}...")
                    try:
                        self._sparse_embedding_model = SparseTextEmbedding(
                            model_name=model_name
                        )
                        self._sparse_model_loaded = True
                        self._sparse_model_load_count += 1
                        self._sparse_model_last_used = time.time()
                        logger.info(
                            f"✅ Sparse Model loaded. (Load count: {self._sparse_model_load_count})"
                        )
                    except Exception as e:
                        logger.error(f"❌ Failed to load Sparse Model: {e}")
                        return None

        return self._sparse_embedding_model

    @property
    def chunker(self) -> HierarchicalChunker:
        if self._chunker is None:
            with self._init_lock:
                if self._chunker is None:
                    self._chunker = HierarchicalChunker()
        # 此时_chunker肯定不是None
        assert self._chunker is not None
        return self._chunker

    def _check_memory_usage(self) -> float:
        """
        检查当前进程内存使用情况
        返回：内存使用量（MB）
        """
        if not PSUTIL_AVAILABLE or psutil is None:
            return 0.0

        # 此时psutil肯定不是None（已经检查过PSUTIL_AVAILABLE和psutil is None）
        assert psutil is not None

        try:
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # 转换为MB
            return memory_mb
        except Exception as e:
            logger.warning(f"⚠️ Memory check failed: {e}")
            return 0.0

    def _should_load_sparse_model(self) -> bool:
        """
        判断是否应该加载稀疏模型
        考虑因素：配置、内存使用、上次使用时间
        """
        # 1. 检查配置是否启用
        if CONFIG_AVAILABLE and SETTINGS and hasattr(SETTINGS, "ENABLE_SPARSE_MODEL"):
            if not SETTINGS.ENABLE_SPARSE_MODEL:
                logger.debug("📉 Sparse model disabled by configuration")
                return False

        # 2. 检查稀疏模型是否可用
        if not SPARSE_MODEL_AVAILABLE:
            return False

        # 3. 检查内存使用情况
        if PSUTIL_AVAILABLE and CONFIG_AVAILABLE and SETTINGS:
            memory_mb = self._check_memory_usage()
            max_memory = getattr(SETTINGS, "MAX_MEMORY_MB", 2048)

            if memory_mb > max_memory * 0.8:  # 超过80%内存限制
                if not self._memory_warning_shown:
                    logger.warning(
                        f"⚠️ High memory usage ({memory_mb:.1f}MB > {max_memory * 0.8:.0f}MB), "
                        "consider disabling sparse model"
                    )
                    self._memory_warning_shown = True
                return False

        # 4. 如果模型已经加载，直接返回
        if self._sparse_model_loaded and self._sparse_embedding_model is not None:
            import time

            self._sparse_model_last_used = time.time()
            return True

        return True

    def unload_sparse_model(self):
        """
        卸载稀疏模型以释放内存
        """
        if self._sparse_embedding_model is not None:
            logger.info("🗑️ Unloading sparse model to free memory")
            self._sparse_embedding_model = None
            self._sparse_model_loaded = False
            # 注意：无法真正释放Python对象内存，但可以允许GC回收

    def _get_sparse_model_name(self) -> str:
        """
        获取当前配置的稀疏模型名称
        """
        if CONFIG_AVAILABLE and SETTINGS and hasattr(SETTINGS, "SPARSE_MODEL_NAME"):
            return SETTINGS.SPARSE_MODEL_NAME
        return DEFAULT_SPARSE_MODEL

    def _estimate_sparse_model_size_mb(self) -> float:
        """
        估算稀疏模型内存占用（MB）

        策略：
        1. 如果模型已加载，尝试使用PyTorch API获取实际内存占用
        2. 否则，根据模型名称映射到已知的近似内存大小
        3. 默认回退到保守估计（500MB）
        """
        # 已知模型名称到近似内存大小（MB）的映射
        MODEL_SIZE_MAPPING = {
            "prithivida/Splade_PP_en_v1": 400.0,
            "naver/splade-cocondenser-ensembledistil": 450.0,
            "default": 500.0,
        }

        model_name = self._get_sparse_model_name()

        # 如果模型已加载，尝试使用PyTorch测量实际内存占用
        if self._sparse_model_loaded and self._sparse_embedding_model is not None:
            try:
                import torch

                # 尝试获取模型对象（假设_sparse_embedding_model有model属性）
                if hasattr(self._sparse_embedding_model, "model"):
                    model = self._sparse_embedding_model.model
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

    def get_sparse_model_stats(self) -> Dict[str, Any]:
        """
        获取稀疏模型统计信息
        """
        model_size_mb = 0.0
        try:
            model_size_mb = self._estimate_sparse_model_size_mb()
        except Exception as e:
            logger.warning(f"⚠️ Failed to estimate sparse model size: {e}")
            # 回退到基于模型名称的保守估计
            model_size_mb = 500.0  # 默认保守估计

        return {
            "loaded": self._sparse_model_loaded,
            "load_count": self._sparse_model_load_count,
            "last_used": self._sparse_model_last_used,
            "memory_warning_shown": self._memory_warning_shown,
            "model_size_mb": round(model_size_mb, 2),
        }

    def _connect(self):
        logger.info(f"🚀 Connecting to Qdrant at {self.host}:{self.port}...")
        try:
            client = QdrantClient(host=self.host, port=self.port)
            self._ensure_collection(client)
            self._client = client
            logger.info("✅ Qdrant Connection Established.")
        except Exception as e:
            logger.critical(f"❌ Qdrant Connection Failed: {e}")
            raise e

    def _ensure_collection(self, client: QdrantClient):
        try:
            collections = client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                logger.info(f"✨ Creating Hybrid Collection: {self.collection_name}")

                vectors_config = {
                    "dense": models.VectorParams(
                        size=1024, distance=models.Distance.COSINE
                    )
                }

                sparse_vectors_config = None
                if SPARSE_MODEL_AVAILABLE:
                    sparse_vectors_config = {
                        "sparse": models.SparseVectorParams(
                            index=models.SparseIndexParams(
                                on_disk=False,
                            )
                        )
                    }

                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=vectors_config,
                    sparse_vectors_config=sparse_vectors_config,
                    hnsw_config=models.HnswConfigDiff(m=16, ef_construct=200),
                )

                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="domain",
                    field_schema=models.KeywordIndexParams(
                        type=models.KeywordIndexType.KEYWORD
                    ),
                )
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="page_id",
                    field_schema=models.KeywordIndexParams(
                        type=models.KeywordIndexType.KEYWORD
                    ),
                )

        except Exception as e:
            logger.error(f"❌ Collection setup failed: {e}")
            raise e

    def add_memory(
        self,
        page_id: str,
        text: str,
        *,
        title: Optional[str] = None,
        domain: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        skip_if_exists: bool = False,
        notion_blocks: Optional[List[Dict]] = None,
    ) -> bool:
        if not text or len(text.strip()) < 5:
            return False

        final_title = title or (metadata or {}).get("title", "Untitled")
        final_domain = domain or (metadata or {}).get("domain", "General")

        if skip_if_exists and self.page_exists(page_id):
            logger.info(f"⏭️ Page exists, skipping: {final_title}")
            return False

        try:
            DOC_STORE.add_document(
                doc_id=page_id,
                content=text,
                metadata={"title": final_title, "domain": final_domain},
            )

            if notion_blocks:
                chunks = self.chunker.chunk_notion_blocks(
                    notion_blocks, page_id, final_title
                )
            else:
                from .hierarchical_chunker import chunk_markdown_hierarchically

                chunks = chunk_markdown_hierarchically(text, page_id, final_title)

            if not chunks:
                return False

            for chunk in chunks:
                self.chunk_cache[chunk.chunk_id] = chunk

            points = []
            contents = [c.content for c in chunks]

            # 兼容处理 Embedding 批量接口
            try:
                dense_vectors = self.embedding_provider.embed_documents(contents)
            except AttributeError:
                dense_vectors = [
                    self.embedding_provider.embed_query(c) for c in contents
                ]

            sparse_vectors = []
            if self.sparse_model:
                sparse_vectors = list(self.sparse_model.embed(contents))

            for i, chunk in enumerate(chunks):
                vector_dict = {"dense": dense_vectors[i]}

                if self.sparse_model and i < len(sparse_vectors):
                    vector_dict["sparse"] = models.SparseVector(
                        indices=sparse_vectors[i].indices.tolist(),
                        values=sparse_vectors[i].values.tolist(),
                    )

                points.append(
                    models.PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id)),
                        vector=vector_dict,
                        payload={
                            "chunk_id": chunk.chunk_id,
                            "page_id": page_id,
                            "content": chunk.content,
                            "title": final_title,
                            "domain": final_domain,
                            "level": chunk.level,
                            "parent_id": chunk.parent_id,
                            "children_ids": chunk.children_ids,
                            "metadata": metadata or {},
                        },
                    )
                )

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="page_id", match=models.MatchValue(value=page_id)
                            )
                        ]
                    )
                ),
            )

            self.client.upsert(collection_name=self.collection_name, points=points)

            logger.info(f"✅ Added {len(points)} chunks (Hybrid) for: {final_title}")
            return True

        except Exception as e:
            logger.error(f"❌ Add memory failed: {e}")
            return False

    def search_memory(
        self,
        query_text: str,
        n_results: int = 3,
        domain: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        results = self.search_with_context(query_text, top_k=n_results, domain=domain)

        if not results["match"] or not results["results"]:
            return {"match": False}

        top_item = results["results"][0]

        return {
            "match": True,
            "title": top_item.get("title"),
            "page_id": top_item.get("page_id"),
            "snippet": top_item.get("content"),
            "content": top_item.get("full_context", top_item.get("content")),
            "score": top_item.get("score"),
            "metadata": top_item.get("metadata"),
        }

    def search_with_context(
        self, query: str, top_k: int = 5, domain: Optional[str] = None
    ) -> Dict[str, Any]:
        if not query or len(query.strip()) < 2:
            return {"match": False, "results": []}

        try:
            query_filter = None
            if domain and domain != "All":
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="domain", match=models.MatchValue(value=domain)
                        )
                    ]
                )

            dense_query = self.embedding_provider.embed_query(query)

            prefetch = []

            prefetch.append(
                models.Prefetch(
                    query=dense_query,
                    using="dense",
                    limit=top_k * 2,
                    filter=query_filter,
                )
            )

            if self.sparse_model:
                sparse_query_list = list(self.sparse_model.embed([query]))
                if sparse_query_list:
                    sparse_vec = models.SparseVector(
                        indices=sparse_query_list[0].indices.tolist(),
                        values=sparse_query_list[0].values.tolist(),
                    )
                    prefetch.append(
                        models.Prefetch(
                            query=sparse_vec,
                            using="sparse",
                            limit=top_k * 2,
                            filter=query_filter,
                        )
                    )

            if len(prefetch) > 1:
                # ✅ 修复：参数名从 method 改为 fusion
                query_struct = models.FusionQuery(
                    fusion=models.Fusion.RRF,
                )
            else:
                query_struct = dense_query

            response = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=prefetch if len(prefetch) > 1 else None,
                query=query_struct,
                limit=top_k,
                with_payload=True,
            )

            points = response.points

            if not points:
                return {"match": False, "results": []}

            results_with_context = []
            for point in points:
                payload = point.payload
                if not payload:
                    continue
                chunk_id = payload.get("chunk_id")

                chunk_obj = self.chunk_cache.get(chunk_id)
                full_context = payload.get("content")

                if chunk_obj:
                    chunk_data = self.chunker.get_chunk_with_context(
                        chunk_id, include_parent=True, include_children=True
                    )
                    if chunk_data:
                        # 此时chunk_data肯定不是None
                        assert chunk_data is not None
                        full_context = chunk_data.get("full_context")

                results_with_context.append(
                    {
                        "chunk_id": chunk_id,
                        "page_id": payload.get("page_id"),
                        "title": payload.get("title"),
                        "content": payload.get("content"),
                        "full_context": full_context,
                        "score": point.score,
                        "level": payload.get("level"),
                        "metadata": payload.get("metadata"),
                    }
                )

            diversity = 0.0
            if results_with_context:
                unique_pages = len(set(r["page_id"] for r in results_with_context))
                diversity = unique_pages / len(results_with_context)

            return {
                "match": True,
                "results": results_with_context,
                "diversity": diversity,
                "query_mode": "hybrid" if self.sparse_model else "dense_only",
            }

        except Exception as e:
            logger.error(f"❌ Hybrid Search Failed: {e}")
            return {"match": False, "results": []}

    def page_exists(self, page_id: str) -> bool:
        try:
            res = self.client.scroll(
                self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="page_id", match=models.MatchValue(value=page_id)
                        )
                    ]
                ),
                limit=1,
            )
            return len(res[0]) > 0
        except Exception:
            return False

    def delete_page(self, page_id: str) -> bool:
        try:
            self.client.delete(
                self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="page_id", match=models.MatchValue(value=page_id)
                            )
                        ]
                    )
                ),
            )
            DOC_STORE.delete_document(page_id)
            return True
        except Exception as e:
            logger.error(f"Failed to delete {page_id}: {e}")
            return False

    def auto_unload_idle_models(self, idle_threshold_seconds: int = 300) -> bool:
        """
        自动卸载闲置模型以释放内存

        参数:
            idle_threshold_seconds: 闲置时间阈值（秒），默认5分钟

        返回:
            bool: 是否有模型被卸载
        """
        unloaded = False
        current_time = time.time()

        # 检查稀疏模型
        if (
            self._sparse_model_loaded
            and self._sparse_embedding_model is not None
            and current_time - self._sparse_model_last_used > idle_threshold_seconds
        ):
            logger.info(
                f"🗑️ Auto-unloading sparse model (idle for "
                f"{int(current_time - self._sparse_model_last_used)}s)"
            )
            self.unload_sparse_model()
            unloaded = True

        return unloaded


_default_store = LevelChunkVectorStore()
add_memory = _default_store.add_memory
search_memory = _default_store.search_memory
search_with_context = _default_store.search_with_context
