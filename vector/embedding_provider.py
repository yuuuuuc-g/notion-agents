"""
vector/embedding_provider.py
定义嵌入模型 (Embedding Model) 的适配器
👉 修复: 增加 input batch size > 64 的自动分批处理
"""
from typing import List, Optional, Union

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

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def name(self) -> str:
        return "SiliconFlow_BGE_M3"

    def _get_embedding(self, text: str) -> List[float]:
        """内部方法：获取单个文本的向量"""
        if not isinstance(text, str):
            text = str(text)

        clean_text = text.replace("\n", " ")
        try:
            response = self.client.embeddings.create(
                model=self.model_name, input=clean_text, encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"❌ Embedding API Error: {e}")
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成向量
        🔥 修复核心：增加分批逻辑，防止触发 413 (Max batch size 64)
        """
        all_embeddings = []
        BATCH_SIZE = 30  # 保险起见，设为 50 (上限是 64)

        # 将 texts 列表切分成多个小批次
        batches = [texts[i : i + BATCH_SIZE] for i in range(0, len(texts), BATCH_SIZE)]

        if len(batches) > 1:
            print(
                f"   ⚡ Splitting {len(texts)} chunks into {len(batches)} batches for embedding..."
            )

        for idx, batch in enumerate(batches):
            clean_batch = [str(t).replace("\n", " ") for t in batch]
            try:
                response = self.client.embeddings.create(
                    model=self.model_name, input=clean_batch, encoding_format="float"
                )
                # 按 index 排序确保顺序一致
                data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [item.embedding for item in data]
                all_embeddings.extend(batch_embeddings)

                # 可选：如果你有大量数据，可以打印进度或稍微 sleep 一下防止 QPS 超限
                # print(f"      - Embedding Batch {idx+1}/{len(batches)} done.")

            except Exception as e:
                print(f"❌ Batch Embedding Error (Batch {idx+1}): {e}")
                # 如果这一批失败了，为了不让程序崩溃，只能填空向量 (或者抛出异常)
                # 这里我们选择填空，但会打印错误
                all_embeddings.extend([[] for _ in range(len(batch))])

        return all_embeddings

    def embed_query(
        self, text: Optional[Union[str, List[str]]] = None, **kwargs
    ) -> List[float]:
        """获取查询向量"""
        final_input = text or kwargs.get("input")
        if isinstance(final_input, list):
            if not final_input:
                return []
            final_input = final_input[0]
        if not final_input:
            return []
        return self._get_embedding(final_input)

    def __call__(self, input: List[str]) -> List[List[float]]:
        return self.embed_documents(input)
