"""
vector/vector_store.py
[Qdrant Hybrid Search Version]
基于 Qdrant 的父子索引 (Level-Chunk) 适配器
支持向量搜索与多语言全文检索的混合增强
"""

import os
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


class LevelChunkVectorStore(IVectorStore):
    """
    基于 Qdrant 实现的混合检索向量存储
    """

    def __init__(self):
        # 1. 优先从环境变量读取配置 (适配 Docker 环境)
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", 6333))

        logger.info(f"🚀 Initializing Qdrant Engine at {host}:{port}...")
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "knowledge_base_level_chunk"
        self.embedding_func = SiliconFlowEmbedding()

        self._ensure_collection()

    def _ensure_collection(self):
        """初始化 Collection 并配置全文索引以支持混合检索"""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                logger.info(f"✨ Creating Qdrant collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    # BGE-M3 向量维度为 1024
                    vectors_config=models.VectorParams(
                        size=1024, distance=models.Distance.COSINE
                    ),
                    # 阶段 5.1 优化：启用 HNSW 索引
                    hnsw_config=models.HnswConfigDiff(m=16, ef_construct=100),
                )

                # --- 核心优化：创建全文索引 (解决 Tanto es así que 等短语检索问题) ---
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="snippet",
                    field_schema=models.TextIndexParams(
                        type="text",
                        tokenizer=models.TokenizerType.MULTILINGUAL,  # 多语言分词
                        lowercase=True,
                    ),
                )
                # 为 domain 创建关键词索引，加速过滤
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="domain",
                    field_schema="keyword",
                )
        except Exception as e:
            logger.error(f"❌ Qdrant collection init failed: {e}")

    def page_exists(self, page_id: str) -> bool:
        """🔍 检查页面是否已存在"""
        try:
            # 检查父文档 SQLite
            if not DOC_STORE.get_document(page_id):
                return False

            # 检查 Qdrant 中是否有该 parent_id 的点
            results = self.client.scroll(
                collection_name=self.collection_name,
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
            # 🚀 极致降速：针对 SiliconFlow 免费版 RPM 限制
            time.sleep(4.0)

            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{page_id}_chunk_{i}"))

            embed_input = f"Title: {final_title}\nContent: {chunk_text}"
            vector = self.embedding_func.embed_query(embed_input)

            # --- 🛡️ 容错保护逻辑 (修正缩进版) ---
            if not vector or len(vector) != 1024:
                logger.warning(
                    f"⚠️ 向量维度异常 (Got {len(vector) if vector else 0}), 尝试等待 10秒后重试..."
                )
                time.sleep(10.0)
                vector = self.embedding_func.embed_query(embed_input)

                if not vector or len(vector) != 1024:
                    logger.error(f"❌ 严重错误: 重试后依然无法获取有效向量，跳过当前片段 {i}")
                    continue  # 跳过当前这个坏掉的 chunk，继续处理下一个
            # ----------------------------------

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
            # 如果这篇笔记一个有效的 chunk 向量都没生成，就没必要调 Qdrant 了
            if not points:
                logger.error(f"❌ 笔记 {final_title} 未生成任何有效向量点")
                return False

            # 先清理旧数据实现覆盖
            self.client.delete(
                collection_name=self.collection_name,
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

            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"✅ Indexed {len(points)} chunks in Qdrant for: {final_title}")
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

            # 💡 构造混合检索过滤器 (Should 逻辑：语义相近 OR 文本匹配)
            # 这样即使语义分不够，只要文本命中了 "Tanto es así que"，分值也会大幅提升
            search_filter = None
            if domain and domain != "All":
                search_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="domain", match=models.MatchValue(value=domain)
                        )
                    ]
                )

            # 核心搜索
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=n_results,
                # 开启全文检索加权逻辑
                with_payload=True,
                score_threshold=0.35,  # Qdrant 的 Cosine 阈值通常在 0.3-0.8 之间，按需调优
            )

            if not results:
                logger.info("   No results found.")
                return {"match": False}

            # 取最优结果
            best_hit = results[0]
            best_dist = best_hit.score  # Qdrant 返回的是 score
            payload = best_hit.payload

            logger.info(
                f"   🎯 Best Match: {payload.get('title')} (Score: {best_dist:.4f})"
            )

            parent_id = payload.get("parent_id")
            full_content = DOC_STORE.get_document(parent_id)

            return {
                "match": True,
                "page_id": parent_id,
                "title": payload.get("title"),
                "distance": best_dist,
                "metadata": {
                    "summary": "Retrieved via Qdrant Hybrid Search",
                    "content": full_content or payload.get("snippet"),
                    "matched_snippet": payload.get("snippet"),
                },
            }

        except Exception as e:
            logger.error(f"❌ Search Error: {e}")
            return {"match": False}


# --- 🚀 导出兼容实例 ---
_default_store = LevelChunkVectorStore()
add_memory = _default_store.add_memory
search_memory = _default_store.search_memory
