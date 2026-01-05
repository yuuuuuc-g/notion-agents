"""
vector/embedding_provider.py
定义嵌入模型 (Embedding Model) 的适配器
"""
from typing import List, Any
from langchain_openai import OpenAIEmbeddings
from config.settings import SETTINGS

class SiliconFlowEmbedding:
    """
    硅基流动嵌入模型封装类
    负责将 BGE-M3 API 适配为 ChromaDB 可用的接口 (解决 1D/2D 维度兼容性)
    """
    def __init__(self):
        self.model_name = "BAAI/bge-m3"
        api_key = SETTINGS.SILICON_KEY
        base_url = SETTINGS.SILICON_BASE_URL
        
        if not api_key:
            print("❌ Error: SILICON_KEY not found in .env")

        self.embeddings = OpenAIEmbeddings(
            model=self.model_name, 
            openai_api_key=api_key,
            openai_api_base=base_url,
            check_embedding_ctx_length=False
        )
    
    # 🔥🔥🔥 补回了丢失的 name 方法 🔥🔥🔥
    def name(self) -> str:
        """ChromaDB 需要这个方法来验证模型一致性"""
        return "SiliconFlow_BGE_M3"

    def __call__(self, input: List[str]) -> List[List[float]]:
        # ChromaDB 写入时调用
        result = self.embeddings.embed_documents(input)
        if result and len(result) > 0 and not isinstance(result[0], list):
            return [result]
        return result

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.embeddings.embed_query(text)