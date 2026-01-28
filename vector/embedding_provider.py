"""
vector/embedding_provider.py
SiliconFlow Embedding Provider
适配 LangChain 接口，支持同步和异步调用
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import httpx
from langchain_core.embeddings import Embeddings

from config.settings import SETTINGS
from utils.logger import get_logger

logger = get_logger(__name__)


class SiliconFlowEmbedding(Embeddings):
    """
    SiliconFlow Embedding Provider

    支持:
    - 同步和异步调用
    - 批量 embedding (性能优化)
    - 并发请求
    - 完善的错误处理
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "BAAI/bge-m3",
        max_workers: int = 5,
    ):
        """
        初始化 SiliconFlow Embedding Provider

        Args:
            api_key: API 密钥 (默认从 SETTINGS 读取)
            base_url: API 基础 URL (默认从 SETTINGS 读取)
            model: Embedding 模型名称
            max_workers: 并发请求的最大线程数
        """
        # 配置
        self.api_key = api_key or SETTINGS.SILICON_KEY
        self.base_url = base_url or SETTINGS.SILICON_BASE_URL
        self.model = model
        self.max_workers = max_workers

        # 验证
        if not self.api_key:
            raise ValueError(
                "SiliconFlow API Key is required. "
                "Set SILICON_KEY in environment or pass api_key parameter."
            )

        if not self.base_url:
            raise ValueError("SiliconFlow base URL is required.")

        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid base_url: {self.base_url}")

        # 客户端 (懒加载)
        self._async_client: Optional[httpx.AsyncClient] = None

        logger.info(f"✅ SiliconFlowEmbedding initialized (model: {self.model})")

    @property
    def async_client(self) -> httpx.AsyncClient:
        """懒加载异步客户端"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=30.0, limits=httpx.Limits(max_keepalive_connections=5)
            )
        return self._async_client

    def embed_query(self, text: str) -> List[float]:
        """
        Embed single query text (同步版本)

        Args:
            text: 查询文本

        Returns:
            Embedding 向量 (1024 维)
        """
        if not text:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {"model": self.model, "input": text, "encoding_format": "float"}

        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=30.0,
            )

            response.raise_for_status()
            data = response.json()

            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
            else:
                logger.error(f"❌ Invalid response format: {data}")
                return []

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout: {e}")
            return []

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            logger.error(f"❌ HTTP {status_code}: {e.response.text}")

            if status_code == 401:
                logger.error("❌ Invalid API key")
            elif status_code == 429:
                logger.warning("⚠️ Rate limit exceeded")

            return []

        except httpx.RequestError as e:
            logger.error(f"❌ Network error: {e}")
            return []

        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple documents (同步版本，使用并发优化)

        Args:
            texts: 文本列表

        Returns:
            Embedding 向量列表
        """
        if not texts:
            return []

        # ✅ 使用线程池并发
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            embeddings = list(executor.map(self.embed_query, texts))

        return embeddings

    async def aembed_query(self, text: str) -> List[float]:
        """
        Embed single query text (异步版本)

        Args:
            text: 查询文本

        Returns:
            Embedding 向量
        """
        if not text:
            return []

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {"model": self.model, "input": text, "encoding_format": "float"}

        try:
            response = await self.async_client.post(
                f"{self.base_url}/embeddings", headers=headers, json=payload
            )

            response.raise_for_status()
            data = response.json()

            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
            else:
                logger.error(f"❌ Invalid response format: {data}")
                return []

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout: {e}")
            return []

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP {e.response.status_code}: {e.response.text}")
            return []

        except httpx.RequestError as e:
            logger.error(f"❌ Network error: {e}")
            return []

        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            return []

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple documents (异步版本，使用并发优化)

        Args:
            texts: 文本列表

        Returns:
            Embedding 向量列表
        """
        if not texts:
            return []

        # ✅ 并发执行
        tasks = [self.aembed_query(text) for text in texts]
        embeddings = await asyncio.gather(*tasks)

        return embeddings

    def __del__(self):
        """清理资源"""
        if self._async_client:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._async_client.aclose())
                else:
                    asyncio.run(self._async_client.aclose())
            except Exception:
                pass
