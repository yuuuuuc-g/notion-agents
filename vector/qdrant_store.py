import os

from qdrant_client import QdrantClient
from qdrant_client.http import models

from utils.logger import get_logger

from .embedding_provider import SiliconFlowEmbedding

logger = get_logger(__name__)


class QdrantVectorStore:
    def __init__(self):
        # 优先读取环境变量，适配 Docker
        host = os.getenv("QDRANT_HOST", "localhost")
        port = int(os.getenv("QDRANT_PORT", 6333))
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = "knowledge_base"
        self.embedding_func = SiliconFlowEmbedding()
        self._init_collection()

    def _init_collection(self):
        # 检查集合是否存在
        collections = self.client.get_collections().collections
        if not any(c.name == self.collection_name for c in collections):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=1024, distance=models.Distance.COSINE
                ),
            )
            # 💡 关键：为全文搜索创建索引，专门对付类似 "Tanto es así que" 的精确短语
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="snippet",
                field_schema=models.TextIndexParams(
                    type="text",
                    tokenizer=models.TokenizerType.MULTILINGUAL,  # 多语言分词
                    lowercase=True,
                ),
            )

    def search_memory(self, query_text: str, n_results: int = 3):
        query_vector = self.embedding_func.embed_query(query_text)

        # 🚀 混合检索逻辑：
        # 1. 向量搜索 (语义)
        # 2. 预过滤/全文匹配 (关键词)
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=n_results,
            # 增加一个“逻辑或”：语义接近 或者 文本包含关键词
            query_filter=models.Filter(
                should=[
                    models.FieldCondition(
                        key="snippet", match=models.MatchText(text=query_text)
                    )
                ]
            )
            if len(query_text) > 5
            else None,  # 短语够长才触发全文增强
        )
        return search_result
