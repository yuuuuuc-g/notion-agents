"""
vector/vector_store.py
[Level-Chunk Refactored to Repository Pattern]
"""

from typing import Any, Dict, Optional

import chromadb

from utils.logger import get_logger

from .doc_store import DOC_STORE

# 引入底层组件
from .embedding_provider import SiliconFlowEmbedding
from .splitter import split_text

# 引入接口定义
from .vector_interface import IVectorStore

logger = get_logger(__name__)


class LevelChunkVectorStore(IVectorStore):
    """
    实现了父子索引策略的向量存储适配器
    """

    def __init__(self, persist_path: str = "./chroma_db"):
        logger.info(f"🚀 Initializing Level-Chunk Vector Engine at {persist_path}...")
        self.embedding_func = SiliconFlowEmbedding()
        self.client = chromadb.PersistentClient(path=persist_path)

        # 重新建库或获取现有库
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base_level_chunk",
            embedding_function=self.embedding_func,
        )

    def page_exists(self, page_id: str) -> bool:
        """
        🔍 检查页面是否已存在于向量库中
        通过检查父文档是否存在以及是否已有对应的 chunk 向量
        """
        try:
            # 检查父文档是否存在于 DOC_STORE
            if DOC_STORE.get_document(page_id):
                # 检查是否有对应的 chunk（至少第一个 chunk）
                chunk_id = f"{page_id}_chunk_0"
                results = self.collection.get(ids=[chunk_id])
                return len(results.get("ids", [])) > 0
            return False
        except Exception as e:
            logger.warning(f"⚠️ [VectorStore] Check page existence error: {e}")
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
        """
        [写入流程] 1. 存父文档 -> 2. 切分 -> 3. 存子向量

        Args:
            skip_if_exists: 如果为 True，且页面已存在，则跳过写入
        """
        if not text or len(text.strip()) < 10:
            return False

        final_metadata = dict(metadata) if metadata else {}
        final_title = title or final_metadata.get("title") or "Untitled"
        final_domain = domain or final_metadata.get("domain") or "General"

        # 🔍 去重检查：如果 skip_if_exists=True 且页面已存在，则跳过
        if skip_if_exists and self.page_exists(page_id):
            logger.info(f"⏭️ [Store] 页面已存在，跳过: {final_title} (ID: {page_id})")
            return False

        # 1. 存父文档 (The Parent) - 使用 REPLACE 确保更新
        logger.info(f"📚 [Store] Saving Parent Document: {final_title} (ID: {page_id})")
        DOC_STORE.add_document(
            doc_id=page_id,
            content=text,
            metadata={
                "title": final_title,
                "domain": final_domain,
                "summary": final_metadata.get("summary", ""),
            },
        )

        # 2. 切分 (The Children)
        chunks = split_text(text)
        logger.info(f"   ✂️ Split into {len(chunks)} child chunks.")
        if not chunks:
            return False

        # 3. 构造子文档数据
        ids, documents, metadatas = [], [], []
        for i, chunk_text in enumerate(chunks):
            import time

            time.sleep(2.0)
            chunk_id = f"{page_id}_chunk_{i}"
            chunk_meta = {
                "parent_id": page_id,
                "chunk_index": i,
                "title": final_title,
                "domain": final_domain,
                "is_child": True,
                "snippet": chunk_text,
            }
            embed_text = f"Title: {final_title}\nContent: {chunk_text}"

            ids.append(chunk_id)
            documents.append(embed_text)
            metadatas.append(chunk_meta)

        try:
            # 🔄 去重处理：先删除已存在的 chunk（如果有更新）
            existing_chunks = self.collection.get(
                ids=[chunk_id for chunk_id in ids],
                include=["documents"],  # 只检查 ID，不加载完整数据
            )
            if existing_chunks.get("ids"):
                logger.info(
                    f"   🔄 删除 {len(existing_chunks['ids'])} 个已存在的 chunk，准备更新..."
                )
                self.collection.delete(ids=existing_chunks["ids"])

            # 使用实例内部的 collection 写入
            self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
            logger.info(f"   ✅ Indexed {len(chunks)} chunks in ChromaDB.")
            return True
        except Exception as e:
            if "403" in str(e):
                time.sleep(10.0)
            logger.error(f"❌ Failed to index vectors: {e}")
            return False

    def search_memory(
        self,
        query_text: str,
        n_results: int = 3,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        [检索流程] 1. 搜 Chroma 子切片 -> 2. 拿 parent_id -> 3. 回表 SQLite 取父文档
        """
        if not query_text or len(query_text.strip()) < 2:
            return {"match": False}

        logger.info(f"🔍 [Level-Chunk Search] Query: {query_text[:20]}...")

        try:
            # 获取向量
            query_vec = self.embedding_func.embed_query(query_text)
            if not query_vec:
                return {"match": False}

            query_args = {"query_embeddings": [query_vec], "n_results": n_results}
            if domain and domain != "All":
                query_args["where"] = {"domain": domain}

            # 搜索子文档
            results = self.collection.query(**query_args)
            if not results["ids"] or len(results["ids"][0]) == 0:
                logger.info("   No results found.")
                return {"match": False}

            # 结果处理 (取 Top 1)
            best_idx = 0
            best_dist = results["distances"][0][best_idx]
            best_meta = results["metadatas"][0][best_idx]
            THRESHOLD = 1.4

            logger.info(
                f"   🎯 Best Match: {best_meta.get('title')} (Dist: {best_dist:.4f})"
            )

            if best_dist < THRESHOLD:
                parent_id = best_meta.get("parent_id")
                snippet = best_meta.get("snippet", "")

                logger.info(
                    f"   🔗 Fetching Parent Document from SQLite: {parent_id}..."
                )
                full_content = DOC_STORE.get_document(parent_id)

                if full_content:
                    logger.info(
                        f"   ✅ Retrieved Full Context ({len(full_content)} chars)."
                    )
                    return {
                        "match": True,
                        "page_id": parent_id,
                        "title": best_meta.get("title"),
                        "distance": best_dist,
                        "metadata": {
                            "summary": "Retrieved via Level-Chunk",
                            "content": full_content,
                            "matched_snippet": snippet,
                        },
                    }
                else:
                    logger.warning("   ⚠️ Parent document missing in SQLite!")
                    return {
                        "match": True,
                        "page_id": parent_id,
                        "metadata": {"content": snippet},
                    }

            return {"match": False}

        except Exception:
            logger.exception("❌ Search Error")
            return {"match": False}


# --- 🚀 关键：为了不破坏 server.py 现有的调用，我们导出一个默认实例 ---
# 这样 server.py 暂时不需要改代码也能跑，同时又完成了类的封装
_default_store = LevelChunkVectorStore()
add_memory = _default_store.add_memory
search_memory = _default_store.search_memory
