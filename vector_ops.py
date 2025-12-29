import os
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from typing import Optional, Dict, Any

load_dotenv()

# --- 配置 Embedding ---
EMBEDDING_FUNC = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-m3", 
    device="cpu"   # "mps", "cuda" 或 "cpu"
)

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=EMBEDDING_FUNC
)

def add_memory(
    page_id: str,
    content: str = None,
    *,
    title: str = None,
    category: str = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    将页面内容存入向量数据库记忆库
    
    参数:
        page_id: Notion 页面 ID，作为向量数据库中的唯一标识
        content: 页面文本内容（必需）
        title: 页面标题（可选，会从 metadata 中获取）
        category: 页面分类（可选，会从 metadata 中获取）
        metadata: 额外的元数据字典，包含 url、summary、type 等信息
    
    返回:
        bool: 成功返回 True，失败返回 False
    """
    # 1. 参数归一化（避免修改原始 metadata 字典，创建副本）
    final_metadata = dict(metadata) if metadata else {}
    
    # 提取标题：优先级 title > metadata["title"] > "Untitled"
    final_title = title or final_metadata.get("title") or "Untitled"
    
    # 提取分类：优先级 category > metadata["category"] > "General"
    final_category = category or final_metadata.get("category") or "General"
    
    # 提取内容
    final_content = content

    # 2. 安全检查
    if not final_content or not isinstance(final_content, str) or len(final_content.strip()) < 10:
        print("❌ VectorOps: content too short or missing, skip memory.")
        return False

    # 3. 准备 Metadata（这里存全量内容，用于 RAG 回答）
    final_metadata.setdefault("title", final_title)
    final_metadata.setdefault("category", final_category)
    final_metadata["content"] = final_content[:4000]  # Metadata 里存多点，供 LLM 查看
    final_metadata.setdefault("url", "")

    # 清洗 None
    cleaned_metadata = {k: str(v) for k, v in final_metadata.items() if v is not None}

    print(f"💾 Vectorizing memory: {final_title}...")

    # 4. 构建高密度 Embedding 文本
    # 策略：
    # 1. 标题最重要，重复两遍以增加权重
    # 2. 摘要次重要
    summary_text = final_metadata.get("summary", "")
    # 新代码: BGE-M3 很能吃，可以放宽到 4000 字符甚至更多
    dense_content = final_content[:3000].replace("\n", " ")
    
    embedding_text = (
        f"Title: {final_title}\n"
        f"Keywords: {final_title} {final_category}\n" # 重复关键词
        f"Summary: {summary_text}\n"
        f"Snippet: {dense_content}"
    )

    # 5. 写入向量数据库
    try:
        collection.add(
            documents=[embedding_text],  # 计算向量只用这个"高密度版"
            metadatas=[cleaned_metadata],
            ids=[page_id],
        )
        print("✅ Memory stored in Vector DB (High-Density Embedding).")
        return True
    except Exception as e:
        print(f"❌ Failed to store vector: {e}")
        return False

def search_memory(
    query_text: str,
    n_results: int = 5,
    category_filter: str = None,
    domain: str = None
) -> Dict[str, Any]:
    """
    从向量数据库中检索相关记忆
    
    参数:
        query_text: 查询文本
        n_results: 返回的结果数量（默认5）
        category_filter: 分类过滤器，None 或 "All" 表示搜索所有分类
    
    返回:
        dict: 包含 match、page_id、title、distance、category、metadata 的字典
              如果未找到匹配，返回 {"match": False}
    """
    if not isinstance(query_text, str) or len(query_text.strip()) < 2:
        return {"match": False}

    print(f"🔍 Vector Searching for: {query_text[:20]}... (Filter: {category_filter})")
    
    query_args = {
        "query_texts": [query_text],
        "n_results": n_results 
    }
    
    # 分类过滤（当 category_filter 为 None 或 "All" 时不添加过滤条件）
    if category_filter and category_filter not in ["All", None]:
        query_args["where"] = {"category": category_filter}

    try:
        results = collection.query(**query_args)
        
        if not results['ids'] or len(results['ids'][0]) == 0:
            print("   No results found.")
            return {"match": False}

        # 遍历 Top-K 结果，找到第一个满足阈值的结果
        count = len(results['ids'][0])
        print(f"   -------- Top {count} Candidates --------")
        
        THRESHOLD = 0.85  # 相似度阈值（距离越小越相似）
        
        for i in range(count):
            dist = results['distances'][0][i]
            meta = results['metadatas'][0][i]
            title = meta.get("title", "Untitled")
            
            print(f"   #{i+1}: {title} (Dist: {dist:.4f})")
            
            if dist < THRESHOLD:
                # 找到第一个满足阈值的结果就返回（Chroma 已按距离排序）
                best_candidate = {
                    "match": True,
                    "page_id": results['ids'][0][i],
                    "title": title,
                    "distance": dist,
                    "category": meta.get("category"),
                    "metadata": meta,
                }
                print(f"   ✅ Selected: {title}")
                return best_candidate
        
        print("❌ No candidate met the threshold.")
        return {"match": False}

    except Exception as e:
        print(f"❌ Vector Search Error: {e}")
        return {"match": False}