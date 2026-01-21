"""
vector/vector_store.py
[Qdrant Hybrid Search Version]
Phase 2.2 Optimization: 单例模式 + 线程安全懒加载
✅ 修复 v4.2: 移除 API 硬阈值，增加分数调试日志，动态过滤结果 (Threshold = 0.52)
"""

import os
import threading
import time
import uuid
from typing import Any, Dict, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models

from utils.logger import get_logger

from .doc_store import DOC_STORE
from .embedding_provider import SiliconFlowEmbedding
from .splitter import split_text
from .vector_interface import IVectorStore

logger = get_logger(__name__)

# 📉 相似度阈值设定
# 0.42 是无关内容的典型分数 (如 DeepSeek vs 西语)
# 0.50 是弱相关
# 0.55 是中等相关 (如 tanto...como...)
# 0.60+ 是强相关
# 我们设置为 0.52，既能过滤掉明显的噪音，又能保留语义相关的结果
SCORE_THRESHOLD = 0.52


class LevelChunkVectorStore(IVectorStore):
    """
    基于 Qdrant 实现的混合检索向量存储
    特性：
    1. 单例模式 (Singleton)
    2. 懒加载 (Lazy Loading)
    3. 线程安全初始化
    """

    _instance = None
    _initialized = False
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super(LevelChunkVectorStore, cls).__new__(cls)
        return cls._instance

    def __init__(self, collection_name: str = None):
        """
        轻量级初始化：只设置配置，不建立连接
        """
        if self._initialized:
            return

        with self._init_lock:
            if self._initialized:
                return

            self.collection_name_config = collection_name or os.getenv(
                "QDRANT_COLLECTION", "biobrain_memories"
            )
            self.host = os.getenv("QDRANT_HOST", "localhost")
            self.port = int(os.getenv("QDRANT_PORT", 6333))

            self._client: Optional[QdrantClient] = None
            self._embedding_func = None

            self._initialized = True
            logger.info("💤 Vector Store initialized (Lazy Mode). Connection deferred.")

    @property
    def client(self) -> QdrantClient:
        """
        懒加载属性：真正需要用的时候才连接数据库
        """
        if self._client is None:
            with self._init_lock:
                if self._client is None:
                    self._connect()
        return self._client

    @property
    def embedding_func(self):
        """懒加载 Embedding 模型"""
        if self._embedding_func is None:
            with self._init_lock:
                if self._embedding_func is None:
                    self._embedding_func = SiliconFlowEmbedding()
        return self._embedding_func

    def _connect(self):
        """执行真实的连接逻辑"""
        logger.info(f"🚀 Connecting to Qdrant at {self.host}:{self.port}...")
        try:
            client = QdrantClient(host=self.host, port=self.port)
            self._ensure_collection(client, self.collection_name_config)
            self._client = client
            logger.info("✅ Qdrant Connection Established.")
        except Exception as e:
            logger.critical(f"❌ Qdrant Connection Failed: {e}")
            raise e

    def _ensure_collection(self, client: QdrantClient, collection_name: str):
        """初始化 Collection 结构"""
        try:
            collections = client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

            if not exists:
                logger.info(f"✨ Creating Qdrant collection: {collection_name}")
                client.create_collection(
                    collection_name=collection_name,
                    # BGE-M3 向量维度 1024
                    vectors_config=models.VectorParams(
                        size=1024, distance=models.Distance.COSINE
                    ),
                    # HNSW 索引优化
                    hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100),
                )

                # 全文索引
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name="snippet",
                    field_schema=models.TextIndexParams(
                        type="text",
                        tokenizer=models.TokenizerType.MULTILINGUAL,
                        lowercase=True,
                    ),
                )
                # Domain 索引
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name="domain",
                    field_schema="keyword",
                )
        except Exception as e:
            logger.error(f"❌ Collection setup failed: {e}")
            raise e

    def page_exists(self, page_id: str) -> bool:
        """检查页面是否存在"""
        try:
            if not DOC_STORE.get_document(page_id):
                return False

            results = self.client.scroll(
                collection_name=self.collection_name_config,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="parent_id", match=models.MatchValue(value=page_id)
                        )
                    ]
                ),
                limit=1,
            )
            return len(results[0]) > 0
        except Exception as e:
            logger.warning(f"⚠️ Check page existence error: {e}")
            return False

    def add_memory(
        self,
        page_id: str,
        text: str,
        *,
        title: str = None,
        domain: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        skip_if_exists: bool = False,
    ) -> bool:
        if not text or len(text.strip()) < 10:
            return False

        final_metadata = dict(metadata) if metadata else {}
        final_title = title or final_metadata.get("title") or "Untitled"
        final_domain = domain or final_metadata.get("domain") or "General"

        if skip_if_exists and self.page_exists(page_id):
            logger.info(f"⏭️ 页面已存在，跳过: {final_title}")
            return False

        # 1. 存父文档 (SQLite)
        DOC_STORE.add_document(
            doc_id=page_id,
            content=text,
            metadata={"title": final_title, "domain": final_domain},
        )

        # 2. 切分 Children
        chunks = split_text(text)
        if not chunks:
            return False

        # 3. 批量写入 Qdrant
        points = []
        for i, chunk_text in enumerate(chunks):
            # 限流保护
            time.sleep(2.0)

            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{page_id}_chunk_{i}"))
            embed_input = f"Title: {final_title}\nContent: {chunk_text}"
            vector = self.embedding_func.embed_query(embed_input)

            # 容错保护
            if not vector or len(vector) != 1024:
                logger.warning("⚠️ 向量维度异常，重试中...")
                time.sleep(10.0)
                vector = self.embedding_func.embed_query(embed_input)
                if not vector or len(vector) != 1024:
                    logger.error(f"❌ 跳过无效片段 {i}")
                    continue

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "parent_id": page_id,
                        "chunk_index": i,
                        "title": final_title,
                        "domain": final_domain,
                        "snippet": chunk_text,
                    },
                )
            )

        try:
            if not points:
                logger.error("❌ 未生成有效向量点")
                return False

            # 清理旧数据
            self.client.delete(
                collection_name=self.collection_name_config,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="parent_id", match=models.MatchValue(value=page_id)
                            )
                        ]
                    )
                ),
            )

            self.client.upsert(
                collection_name=self.collection_name_config, points=points
            )
            logger.info(f"✅ Indexed {len(points)} chunks: {final_title}")
            return True
        except Exception as e:
            logger.error(f"❌ Qdrant upload failed: {e}")
            return False

    def search_memory(
        self,
        query_text: str,
        n_results: int = 3,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not query_text or len(query_text.strip()) < 2:
            return {"match": False}

        logger.info(f"🔍 [Hybrid Search] Query: {query_text}")

        try:
            query_vector = self.embedding_func.embed_query(query_text)

            search_filter = None
            if domain and domain != "All":
                search_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="domain", match=models.MatchValue(value=domain)
                        )
                    ]
                )

            # 🔥 1. 移除 score_threshold，获取原始结果
            response = self.client.query_points(
                collection_name=self.collection_name_config,
                query=query_vector,
                query_filter=search_filter,
                limit=n_results,
                with_payload=True,
                # score_threshold=0.65,  <-- 已移除硬编码阈值
            )

            results = response.points

            if not results:
                logger.info("   ℹ️ No results found (Raw).")
                return {"match": False}

            best_hit = results[0]
            best_dist = best_hit.score
            payload = best_hit.payload

            # 🔥 2. 打印真实分数，方便调试
            logger.info(
                f"   🎯 Raw Match: {payload.get('title')} (Score: {best_dist:.4f})"
            )

            # 🔥 3. 手动应用更合理的阈值 (0.52)
            if best_dist < SCORE_THRESHOLD:
                logger.info(
                    f"   🗑️ Filtered out: Score {best_dist:.4f} < Threshold {SCORE_THRESHOLD}"
                )
                return {"match": False}

            logger.info("   ✅ Match Accepted.")

            parent_id = payload.get("parent_id")
            from .doc_store import DOC_STORE

            full_content = DOC_STORE.get_document(parent_id)

            return {
                "match": True,
                "page_id": parent_id,
                "title": payload.get("title"),
                "distance": best_dist,
                "metadata": {
                    "summary": "Retrieved via Qdrant query_points",
                    "content": full_content or payload.get("snippet"),
                    "matched_snippet": payload.get("snippet"),
                },
            }

        except Exception as e:
            logger.error(f"❌ Search Error: {e}")
            return {"match": False}


# 导出兼容实例
_default_store = LevelChunkVectorStore()
add_memory = _default_store.add_memory
search_memory = _default_store.search_memory
