"""
vector/embedding_provider.py
定义嵌入模型 (Embedding Model) 的适配器
"""
from typing import List, Optional, Any, Union
from openai import OpenAI  
from config.settings import SETTINGS

class SiliconFlowEmbedding:
    """
    硅基流动嵌入模型封装类
    负责将 BGE-M3 API 适配为 ChromaDB 和 LangChain 可用的接口
    """
    def __init__(self):
        self.model_name = "BAAI/bge-m3"
        api_key = SETTINGS.SILICON_KEY
        base_url = SETTINGS.SILICON_BASE_URL
        
        if not api_key:
            print("❌ Error: SILICON_KEY not found in .env")

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    def name(self) -> str:
        return "SiliconFlow_BGE_M3"

    # 用于将单个文本字符串转换为对应的向量嵌入（embedding），通常用于后续在向量数据库中检索或相似度比对。
    def _get_embedding(self, text: str) -> List[float]:
        """内部方法：获取单个文本的向量"""
        # 🔥 防御性编程：确保 text 是字符串
        if not isinstance(text, str):
            text = str(text)
            
        clean_text = text.replace("\n", " ")
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=clean_text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Embedding API Error: {e}")
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量生成向量"""
        clean_texts = [str(t).replace("\n", " ") for t in texts]
        try:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=clean_texts,
                encoding_format="float"
            )
            data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in data]
        except Exception as e:
            print(f"❌ Batch Embedding Error: {e}")
            return []


    def embed_query(self, text: Optional[Union[str, List[str]]] = None, **kwargs) -> List[float]:
        """
        获取查询向量
        🔥 修复：兼容 list 类型的输入 (防止 LangChain 传入 list 导致报错)
        """
        final_input = text or kwargs.get("input")
        
        # 处理 list 输入的情况 (取第一个元素)
        if isinstance(final_input, list):
            if not final_input: return []
            final_input = final_input[0]
            
        if not final_input:
            return []
            
        return self._get_embedding(final_input)

    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.embed_documents(input)