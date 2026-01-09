"""
vector/vector_store.py
[Level-Chunk Refactored]
实现了 "父子索引" (Parent-Child Indexing) 策略：
1. Write: 父文档存 SQLite -> 切分 -> 子文档存 ChromaDB (带 parent_id)
2. Read:  搜子文档 -> 拿 parent_id -> 回表 SQLite 取父文档 -> 返回完整上下文
"""
import chromadb
from typing import Optional, Dict, Any

# 👇 引入我们的新组件
from .embedding_provider import SiliconFlowEmbedding
from .doc_store import DOC_STORE
from .splitter import split_text

# --- 全局初始化 ---
print("🚀 Initializing Level-Chunk Vector Engine...")
EMBEDDING_FUNC = SiliconFlowEmbedding()

client = chromadb.PersistentClient(path="./chroma_db")

# 重新建库
collection = client.get_or_create_collection(
    name="knowledge_base_level_chunk", # 改个名，防止和旧数据混淆
    embedding_function=EMBEDDING_FUNC
)

# --- 业务逻辑 ---

def add_memory(
    page_id: str,
    text: str, 
    *,
    title: str = None,
    domain: str = None, 
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    [写入流程升级]
    1. 保存父文档 (Full Text) 到 DocStore
    2. 切分成子文档 (Chunks)
    3. 向量化子文档并存入 Chroma
    """
    if not text or len(text.strip()) < 10: return False

    final_metadata = dict(metadata) if metadata else {}
    final_title = title or final_metadata.get("title") or "Untitled"
    final_domain = domain or final_metadata.get("domain") or "General"
    
    # -----------------------------------------------------
    # 步骤 1: 存父文档 (The Parent)
    # -----------------------------------------------------
    print(f"📚 [Store] Saving Parent Document: {final_title} (ID: {page_id})")
    DOC_STORE.add_document(
        doc_id=page_id,
        content=text,
        metadata={
            "title": final_title,
            "domain": final_domain,
            "summary": final_metadata.get("summary", "")
        }
    )

    # -----------------------------------------------------
    # 步骤 2: 切分 (The Children)
    # -----------------------------------------------------
    chunks = split_text(text)
    print(f"   ✂️ Split into {len(chunks)} child chunks.")

    if not chunks:
        return False

    # -----------------------------------------------------
    # 步骤 3: 存子向量 (Indexing)
    # -----------------------------------------------------
    ids = []
    documents = []
    metadatas = []

    for i, chunk_text in enumerate(chunks):
        # 构造子文档 ID: 父ID_索引
        chunk_id = f"{page_id}_chunk_{i}"
        
        # 构造子文档 Metadata (必须包含 parent_id)
        chunk_meta = {
            "parent_id": page_id,      # 👈 核心：指向爸爸的指针
            "chunk_index": i,
            "title": final_title,
            "domain": final_domain,
            "is_child": True,
            # 可选：把这一小段文本也存着，方便调试看 match 了哪一句
            "snippet": chunk_text 
        }

        # 构造用于 Embedding 的文本 (加点语义前缀效果更好)
        embed_text = f"Title: {final_title}\nContent: {chunk_text}"

        ids.append(chunk_id)
        documents.append(embed_text)
        metadatas.append(chunk_meta)

    try:
        # 批量写入 Chroma
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        print(f"   ✅ Indexed {len(chunks)} chunks in ChromaDB.")
        return True
    except Exception as e:
        print(f"❌ Failed to index vectors: {e}")
        return False

def search_memory(
    query_text: str,
    n_results: int = 3, # 只需要找前 3 个最相关的点
    domain: Optional[str] = None
) -> Dict[str, Any]:
    """
    [检索流程升级]
    1. 搜 Chroma 找到最相关的子切片
    2. 拿到 parent_id
    3. 去 DocStore 取回完整的父文档
    """
    if not query_text or len(query_text.strip()) < 2: return {"match": False}

    print(f"🔍 [Level-Chunk Search] Query: {query_text[:20]}...")
    
    try:
        # --- 1. 获取向量 (保持之前的修复逻辑) ---
        query_vec = EMBEDDING_FUNC.embed_query(query_text)
        if not query_vec: return {"match": False}
        
        query_args = {
            "query_embeddings": [query_vec], 
            "n_results": n_results
        }
        if domain and domain != "All":
            query_args["where"] = {"domain": domain}

        # --- 2. 搜索子文档 ---
        results = collection.query(**query_args)

        if not results["ids"] or len(results["ids"][0]) == 0:
            print("   No results found.")
            return {"match": False}

        # --- 3. 结果处理 (子 -> 父) ---
        # 我们取相关度最高的一个结果 (Top 1)
        best_idx = 0
        best_dist = results["distances"][0][best_idx]
        best_meta = results["metadatas"][0][best_idx]
        
        THRESHOLD = 1.4 # 阈值可微调
        
        print(f"   🎯 Best Match: {best_meta.get('title')} (Dist: {best_dist:.4f})")

        if best_dist < THRESHOLD:
            # 🔥 核心时刻：通过儿子找爸爸
            parent_id = best_meta.get("parent_id")
            snippet = best_meta.get("snippet", "")
            
            print(f"   🔗 Fetching Parent Document from SQLite: {parent_id}...")
            full_content = DOC_STORE.get_document(parent_id)
            
            if full_content:
                print(f"   ✅ Retrieved Full Context ({len(full_content)} chars).")
                return {
                    "match": True,
                    "page_id": parent_id,
                    "title": best_meta.get("title"),
                    "distance": best_dist,
                    # 返回给 Agent 的 metadata
                    "metadata": {
                        "summary": "Retrieved via Level-Chunk",
                        # Agent 会读到这个完整的 content
                        "content": full_content, 
                        # 同时也提供刚才命中的那个小片段，方便高亮或调试
                        "matched_snippet": snippet 
                    }
                }
            else:
                print("   ⚠️ Parent document missing in SQLite!")
                # 降级方案：只返回碎片
                return {
                    "match": True,
                    "page_id": parent_id,
                    "metadata": {"content": snippet}
                }

        return {"match": False}

    except Exception as e:
        print(f"❌ Search Error: {e}")
        import traceback
        traceback.print_exc() 
        return {"match": False}