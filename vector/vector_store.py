"""
vector/vector_store.py
负责 ChromaDB 的具体操作 (增删改查)，引用 embedding_provider 进行向量化
"""
import chromadb
from typing import Optional, Dict, Any
from config.settings import SETTINGS

# 👇 引用旁边的 embedding_provider
from .embedding_provider import SiliconFlowEmbedding

# --- 全局初始化 ---
print("🚀 Initializing SiliconFlow BGE-M3 Embedding...")
EMBEDDING_FUNC = SiliconFlowEmbedding()

# 创建 ChromaDB 客户端
# 注意：这里路径写 "./chroma_db"，是相对于运行根目录 (server.py 所在目录) 的
client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(
    name="knowledge_base_v2", 
    embedding_function=EMBEDDING_FUNC
)

# --- 业务逻辑 (add / search) ---

def add_memory(
    page_id: str,
    text: str, 
    *,
    title: str = None,
    domain: str = None, 
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """写入记忆"""
    final_metadata = dict(metadata) if metadata else {}
    final_title = title or final_metadata.get("title") or "Untitled"
    final_domain = domain or final_metadata.get("domain") or "General"

    if not text or len(text.strip()) < 10: return False

    final_metadata["title"] = final_title
    final_metadata["domain"] = final_domain
    final_metadata["content"] = text[:3000]
    final_metadata.setdefault("url", "")
    
    # 清洗 metadata (转字符串，去 None)
    cleaned_metadata = {k: str(v) for k, v in final_metadata.items() if v is not None}

    print(f"💾 Vectorizing memory: {final_title}...")
    
    # 构造富文本
    embedding_text = f"Title: {final_title}\nSummary: {final_metadata.get('summary','')}\nSnippet: {text[:3000].replace('\n', ' ')}"

    try:
        collection.add(
            documents=[embedding_text],
            metadatas=[cleaned_metadata],
            ids=[page_id],
        )
        print("✅ Memory stored in Vector DB (SiliconFlow).")
        return True
    except Exception as e:
        print(f"❌ Failed to store vector: {e}")
        return False

def search_memory(
    query_text: str,
    n_results: int = 5,
    domain: Optional[str] = None
) -> Dict[str, Any]:
    """检索记忆"""
    if not query_text or len(query_text.strip()) < 2: return {"match": False}

    filter_msg = domain if domain and domain != "All" else "None"
    print(f"🔍 Vector Searching for: {query_text[:20]}... (Filter: {filter_msg})")
    
    query_args = {
        "query_texts": [query_text],
        "n_results": n_results
    }
    
    if domain and domain not in ["All", None]:
        query_args["where"] = {"domain": domain}

    try:
        results = collection.query(**query_args)

        if not results["ids"] or len(results["ids"][0]) == 0:
            print("   No results found.")
            return {"match": False}

        count = len(results["ids"][0])
        print(f"   -------- Top {count} Candidates --------")
        
        THRESHOLD = 1.5 

        for i in range(count):
            dist = results["distances"][0][i]
            meta = results["metadatas"][0][i]
            title = meta.get("title", "Untitled")
            print(f"   #{i+1}: {title} (Dist: {dist:.4f})")

            if dist < THRESHOLD:
                print(f"   ✅ Selected: {title}")
                return {
                    "match": True,
                    "page_id": results["ids"][0][i],
                    "title": title,
                    "distance": dist,
                    "metadata": meta,
                }
        
        return {"match": False}

    except Exception as e:
        print(f"❌ Vector Search Error: {e}")
        return {"match": False}