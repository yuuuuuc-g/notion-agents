import os
import chromadb
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List
from langchain_openai import OpenAIEmbeddings 

load_dotenv()

# --- 🔥 核心修改：自定义适配器类 ---
# 这是一个“胶水”类，负责把 ChromaDB 的请求转发给 OpenRouter
class OpenRouterEmbeddingFunction:
    def __init__(self):
        # 初始化 LangChain 的 Embedding 工具
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        
        if not api_key:
            # 防止没有 key 时报错，给一个假 key 占位（运行时会抛错，但启动不崩）
            print("⚠️ Warning: OPENAI_API_KEY not found in environment.")
            api_key = "sk-placeholder"

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small", # OpenRouter 支持的高性价比模型
            openai_api_key=api_key,
            openai_api_base=api_base,
            check_embedding_ctx_length=False
        )

    # ChromaDB 要求的标准接口：接收文本列表，返回向量列表
    def __call__(self, input: List[str]) -> List[List[float]]:
        # 调用 API 生成向量
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

    # 3. 准备 Metadata 
    final_metadata.setdefault("title", final_title)
    final_metadata.setdefault("domain", final_domain) 
    final_metadata.setdefault("category", final_domain) 
    
    # 截取正文存入 metadata
    final_metadata["content"] = text[:3000] 
    final_metadata.setdefault("url", "")

    # 清洗 None 
    cleaned_metadata = {k: str(v) for k, v in final_metadata.items() if v is not None}

    print(f"💾 Vectorizing memory: {final_title}...")

    # 4. 构建 Embedding 文本
    summary_text = final_metadata.get("summary", "")
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
    domain: str = None 
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
    
    if domain and domain not in ["All", None]:
        query_args["where"] = {"domain": domain}

    try:
        results = collection.query(**query_args)
        
        if not results['ids'] or len(results['ids'][0]) == 0:
            print("   No results found.")
            return {"match": False}

        # 遍历 Top-K 结果
        count = len(results['ids'][0])
        print(f"   -------- Top {count} Candidates --------")
        
        # 🔥 修改点4：OpenAI Embedding 的余弦距离通常较小
        THRESHOLD = 0.7  
        
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