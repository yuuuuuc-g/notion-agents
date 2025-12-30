import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from typing import Optional, Dict, Any

load_dotenv()

# --- 配置 Embedding ---
EMBEDDING_FUNC = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-m3", 
    device="cpu"   # "mps" (Mac), "cuda" (NVIDIA), 或 "cpu"
)

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=EMBEDDING_FUNC
)

def add_memory(
    page_id: str,
    text: str, # <--- 🔥 修改点1：改名为 text，对应 tools.py
    *,
    title: str = None,
    domain: str = None, # <--- 🔥 修改点2：改名为 domain，对应 tools.py
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    将页面内容存入向量数据库记忆库
    """
    # 1. 参数归一化
    final_metadata = dict(metadata) if metadata else {}
    
    # 提取标题
    final_title = title or final_metadata.get("title") or "Untitled"
    
    # 提取分类/领域
    final_domain = domain or final_metadata.get("domain") or "General"
    
    # 2. 安全检查
    if not text or not isinstance(text, str) or len(text.strip()) < 10:
        print("❌ VectorOps: content too short or missing, skip memory.")
        return False

    # 3. 准备 Metadata (存入 ChromaDB 供后续检索参考)
    final_metadata.setdefault("title", final_title)
    final_metadata.setdefault("domain", final_domain) # 统一存为 domain
    # 兼容性处理：如果旧代码用了 category，也存一份
    final_metadata.setdefault("category", final_domain) 
    
    # 截取正文存入 metadata，供 RAG 上下文使用 (限制长度防止元数据过大)
    final_metadata["content"] = text[:3000] 
    final_metadata.setdefault("url", "")

    # 清洗 None (ChromaDB 不允许 metadata 值为 None)
    cleaned_metadata = {k: str(v) for k, v in final_metadata.items() if v is not None}

    print(f"💾 Vectorizing memory: {final_title}...")

    # 4. 构建高密度 Embedding 文本 (策略：标题加权 + 摘要 + 正文)
    summary_text = final_metadata.get("summary", "")
    # 移除换行符，减少噪声
    dense_content = text[:3000].replace("\n", " ")
    
    embedding_text = (
        f"Title: {final_title}\n"
        f"Keywords: {final_title} {final_domain}\n"
        f"Summary: {summary_text}\n"
        f"Snippet: {dense_content}"
    )

    # 5. 写入向量数据库
    try:
        collection.add(
            documents=[embedding_text],
            metadatas=[cleaned_metadata],
            ids=[page_id],
        )
        print("✅ Memory stored in Vector DB.")
        return True
    except Exception as e:
        print(f"❌ Failed to store vector: {e}")
        return False

def search_memory(
    query_text: str,
    n_results: int = 5,
    domain: str = None # <--- 🔥 修改点3：统一使用 domain 参数
) -> Dict[str, Any]:
    """
    从向量数据库中检索相关记忆
    """
    if not isinstance(query_text, str) or len(query_text.strip()) < 2:
        return {"match": False}

    filter_msg = domain if domain and domain != "All" else "None"
    print(f"🔍 Vector Searching for: {query_text[:20]}... (Filter: {filter_msg})")
    
    query_args = {
        "query_texts": [query_text],
        "n_results": n_results 
    }
    
    # 分类过滤
    # 注意：ChromaDB 的 where 过滤字段必须在 metadata 里存在
    if domain and domain not in ["All", None]:
        # 这里为了兼容，你可以同时检查 domain 或 category
        # 但通常我们在 add_memory 里已经统一存了 'domain'
        query_args["where"] = {"domain": domain}

    try:
        results = collection.query(**query_args)
        
        if not results['ids'] or len(results['ids'][0]) == 0:
            print("   No results found.")
            return {"match": False}

        # 遍历 Top-K 结果
        count = len(results['ids'][0])
        print(f"   -------- Top {count} Candidates --------")
        
        THRESHOLD = 0.85  # 🔥 修改点4：BGE-M3 的距离可能比较大，建议先放宽阈值观察，或者设为 1.0 (不过滤)
        # Chroma 默认是 L2 距离，越小越相似。0.85 是个经验值，如果搜不到可以调大到 1.2
        
        for i in range(count):
            dist = results['distances'][0][i]
            meta = results['metadatas'][0][i]
            title = meta.get("title", "Untitled")
            
            print(f"   #{i+1}: {title} (Dist: {dist:.4f})")
            
            if dist < THRESHOLD:
                best_candidate = {
                    "match": True,
                    "page_id": results['ids'][0][i],
                    "title": title,
                    "distance": dist,
                    "metadata": meta,
                }
                print(f"   ✅ Selected: {title}")
                return best_candidate
        
        print("❌ No candidate met the threshold.")
        return {"match": False}

    except Exception as e:
        print(f"❌ Vector Search Error: {e}")
        return {"match": False}