"""
vector/embedding_provider.py
SiliconFlow Embedding Provider v2
适配 LangChain 接口，支持同步和异步调用

修复:
  - 删除 __del__（asyncio.get_event_loop 在 shutdown 期间不可靠）
    → 异步 client 的关闭交给 server.py lifespan shutdown
  - ThreadPoolExecutor 提升为实例变量（懒加载），避免每次调用都创建新的
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
    - 批量 embedding（并发优化）
    - 完善的错误处理
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "BAAI/bge-m3",
        max_workers: int = 5,
    ):
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

        # 懒加载占位
        self._async_client: Optional[httpx.AsyncClient] = None
        self._thread_pool: Optional[ThreadPoolExecutor] = None  # 🔥 新增

        # 复用的请求头（不变，提取一次）
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"✅ SiliconFlowEmbedding initialized (model: {self.model})")

    # ── 懒加载 properties ──────────────────────────
    @property
    def async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(max_keepalive_connections=5),
            )
        return self._async_client

    @property
    def thread_pool(self) -> ThreadPoolExecutor:  # 🔥 新增
        if self._thread_pool is None:
            self._thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._thread_pool

    async def close(self):  # 🔥 新增
        """显式关闭资源。由 server.py lifespan shutdown 调用。"""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
        if self._thread_pool:
            self._thread_pool.shutdown(wait=False)
            self._thread_pool = None

    # ── 同步路径 ─────────────────────────────────────
    def embed_query(self, text: str) -> List[float]:
        """Embed single query text（同步）"""
        if not text:
            return []

        payload = {"model": self.model, "input": text, "encoding_format": "float"}

        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                headers=self._headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]

            logger.error(f"❌ Invalid response format: {data}")
            return []

        except httpx.TimeoutException as e:
            logger.error(f"❌ Timeout: {e}")
            return []
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.error(f"❌ HTTP {status}: {e.response.text}")
            if status == 401:
                logger.error("❌ Invalid API key")
            elif status == 429:
                logger.warning("⚠️ Rate limit exceeded")
            return []
        except httpx.RequestError as e:
            logger.error(f"❌ Network error: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}", exc_info=True)
            return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents（同步并发）"""
        if not texts:
            return []

        # 🔥 复用实例级 thread_pool，不再每次 with 创建新的
        return list(self.thread_pool.map(self.embed_query, texts))

    # ── 异步路径 ─────────────────────────────────────
    async def aembed_query(self, text: str) -> List[float]:
        """Embed single query text（异步）"""
        if not text:
            return []

        payload = {"model": self.model, "input": text, "encoding_format": "float"}

        try:
            response = await self.async_client.post(
                f"{self.base_url}/embeddings",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]

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
        """Embed multiple documents（异步并发）"""
        if not texts:
            return []

        tasks = [self.aembed_query(text) for text in texts]
        return list(await asyncio.gather(*tasks))

    # 🔥 删除了 __del__
    # 原因：
    #   1. asyncio.get_event_loop() 在 Python 3.10+ shutdown 期间抛 DeprecationWarning
    #   2. 如果 loop 已关闭会抛 RuntimeError
    #   3. __del__ 执行时机不确定，不适合做 IO 清理
    # 替代：调用 close() 方法，由 server.py lifespan 管理
