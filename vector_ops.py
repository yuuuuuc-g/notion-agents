import os
import chromadb
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
from langchain_openai import OpenAIEmbeddings 

load_dotenv()

# --- 核心修改：自定义 Embedding Function 适配器 ---
class OpenRouterEmbeddingFunction:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        
        if not api_key:
            print("⚠️ Warning: OPENAI_API_KEY not found in environment.")
            api_key = "sk-placeholder"

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=api_key,
            openai_api_base=api_base,
            check_embedding_ctx_length=False
        )
    # Chroma 需要的 name 属性
    def name(self):
        return "OpenRouterEmbeddingFunction"

    # ✅ 规范化参数名（texts）
    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(input)

# --- 配置 Embedding ---
EMBEDDING_FUNC = OpenRouterEmbeddingFunction()

# 初始化客户端
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="knowledge_base",
    embedding_function=EMBEDDING_FUNC
)

def add_memory(
    page_id: str,
    text: str, 
    *,
    title: str = None,
    domain: str = None, 
    metadata: Optional[Dict[str, Any]] = None,
):
    """
    将页面内容存入向量数据库
    """
    final_metadata = dict(metadata) if metadata else {}

    final_title = title or final_metadata.get("title") or "Untitled"
    final_domain = domain or final_metadata.get("domain") or "General"

    if not text or not isinstance(text, str) or len(text.strip()) < 10:
        print("❌ VectorOps: content too short or missing, skip memory.")
        return False

    # ✅ 只保留 domain 作为唯一分类字段
    final_metadata["title"] = final_title
    final_metadata["domain"] = final_domain
    final_metadata["content"] = text[:3000]
    final_metadata.setdefault("url", "")

    cleaned_metadata = {k: str(v) for k, v in final_metadata.items() if v is not None}

    print(f"💾 Vectorizing memory: {final_title}...")

    summary_text = final_metadata.get("summary", "")
    dense_content = text[:3000].replace("\n", " ")

    embedding_text = (
        f"Title: {final_title}\n"
        f"Domain: {final_domain}\n"
        f"Summary: {summary_text}\n"
        f"Snippet: {dense_content}"
    )

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
    domain: Optional[str] = None
) -> Dict[str, Any]:
    """
    从向量数据库中检索相关记忆（唯一标准接口）
    """
    if not isinstance(query_text, str) or len(query_text.strip()) < 2:
        return {"match": False}

    filter_msg = domain if domain and domain != "All" else "None"
    print(f"🔍 Vector Searching for: {query_text[:20]}... (Filter: {filter_msg})")
    
    query_args = {
        "query_texts": [query_text],
        "n_results": n_results
    }
    
    # ✅ 统一只使用 domain 过滤
    if domain and domain not in ["All", None]:
        query_args["where"] = {"domain": domain}

    try:
        results = collection.query(**query_args)

        if not results["ids"] or len(results["ids"][0]) == 0:
            print("   No results found.")
            return {"match": False}

        count = len(results["ids"][0])
        print(f"   -------- Top {count} Candidates --------")

        THRESHOLD = 0.7

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

        print("❌ No candidate met the threshold.")
        return {"match": False}

    except Exception as e:
        print(f"❌ Vector Search Error: {e}")
        return {"match": False}