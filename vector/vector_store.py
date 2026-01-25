"""
vector/vector_store.py
[Qdrant Hybrid Search Native Version]
版本：v5.1 (Fix FusionQuery Param)
修复：models.FusionQuery 参数名从 method 修正为 fusion
"""

import os
import threading
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from utils.logger import get_logger

from .doc_store import DOC_STORE
from .embedding_provider import SiliconFlowEmbedding
from .hierarchical_chunker import HierarchicalChunk, HierarchicalChunker
from .vector_interface import IVectorStore

# 尝试导入稀疏向量模型
try:
    from fastembed import SparseTextEmbedding

    SPARSE_MODEL_AVAILABLE = True
except ImportError:
    SPARSE_MODEL_AVAILABLE = False

logger = get_logger(__name__)

# 默认稀疏模型
SPARSE_MODEL_NAME = "prithivida/Splade_PP_en_v1"


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

    def __init__(self, collection_name: str = None):
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
            self._embedding_provider = None
            self._sparse_embedding_model = None
            self._chunker = None
            self.chunk_cache: Dict[str, HierarchicalChunk] = {}

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
        return self._client

    @property
    def embedding_provider(self):
        if self._embedding_provider is None:
            with self._init_lock:
                if self._embedding_provider is None:
                    self._embedding_provider = SiliconFlowEmbedding()
        return self._embedding_provider

    @property
    def sparse_model(self):
        if not SPARSE_MODEL_AVAILABLE:
            return None

        if self._sparse_embedding_model is None:
            with self._init_lock:
                if self._sparse_embedding_model is None:
                    logger.info(f"⏳ Loading Sparse Model: {SPARSE_MODEL_NAME}...")
                    try:
                        self._sparse_embedding_model = SparseTextEmbedding(
                            model_name=SPARSE_MODEL_NAME
                        )
                        logger.info("✅ Sparse Model loaded.")
                    except Exception as e:
                        logger.error(f"❌ Failed to load Sparse Model: {e}")
                        return None
        return self._sparse_embedding_model

    @property
    def chunker(self):
        if self._chunker is None:
            with self._init_lock:
                if self._chunker is None:
                    self._chunker = HierarchicalChunker()
        return self._chunker

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
                    field_schema="keyword",
                )
                client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="page_id",
                    field_schema="keyword",
                )

        except Exception as e:
            logger.error(f"❌ Collection setup failed: {e}")
            raise e

    def add_memory(
        self,
        page_id: str,
        text: str,
        *,
        title: str = None,
        domain: str = None,
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
                chunk_id = payload.get("chunk_id")

                chunk_obj = self.chunk_cache.get(chunk_id)
                full_context = payload.get("content")

                if chunk_obj:
                    chunk_data = self.chunker.get_chunk_with_context(
                        chunk_id, include_parent=True, include_children=True
                    )
                    if chunk_data:
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


_default_store = LevelChunkVectorStore()
add_memory = _default_store.add_memory
search_memory = _default_store.search_memory
search_with_context = _default_store.search_with_context
