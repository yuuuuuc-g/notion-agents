"""
utils/cache_fallback.py
Redis 缓存降级包装器
功能：
1. 包装 Redis 操作 (get, setex, exists, delete)，在 Redis 挂掉时不抛出异常
2. Redis 不可用时使用进程内 TTL 字典作为后端，避免依赖注入或路由层 500
3. 提供后台健康检查，自动恢复连接状态
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional, Tuple

import redis

logger = logging.getLogger(__name__)

# value, expire_at (epoch seconds；未使用 Redis 时仅依赖此项)
_MemoryEntry = Tuple[str, float]


class CacheWithFallback:
    """带熔断/降级机制的缓存包装器"""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        # 中文说明：在 Container 构造阶段可能传入 None（Redis 首轮即连不上），此时直接进入仅内存模式，禁止向路由层冒泡 ConnectionError
        self.redis_client = redis_client
        self.is_available = redis_client is not None
        self._check_task = None
        self._memory: Dict[str, _MemoryEntry] = {}

    def _degrade_to_memory_only(self, operation: str, exc: Exception) -> None:
        if self.is_available:
            logger.error(
                "❌ [Cache] Redis 在 %s 时失败，切换为仅内存模式 (No Redis): %s",
                operation,
                exc,
                exc_info=True,
            )
            self.is_available = False

    def _memory_get(self, key: str) -> Optional[str]:
        if key not in self._memory:
            return None
        val, exp = self._memory[key]
        if exp < time.time():
            del self._memory[key]
            return None
        return val

    def _memory_setex(self, key: str, ttl: int, value: str) -> bool:
        self._memory[key] = (value, time.time() + float(ttl))
        return True

    def _memory_delete(self, key: str) -> None:
        self._memory.pop(key, None)

    async def start_health_check(self):
        """
        后台任务：定期检查 Redis 健康状态
        """
        logger.info("💓 [Cache] 启动 Redis 健康检查...")
        while True:
            try:
                await asyncio.sleep(30)  # 每 30 秒检查一次

                if self.redis_client is None:
                    try:
                        from infrastructure.cache.redis_client import RedisClient

                        self.redis_client = RedisClient.get_instance()
                        self.is_available = True
                        logger.info("✅ [Cache] Redis 重新连接成功 (lazy recovery)")
                    except redis.RedisError as e:
                        logger.debug("Redis 仍不可用 (health check): %s", e)
                    continue

                self.redis_client.ping()

                if not self.is_available:
                    logger.info("✅ [Cache] Redis 恢复可用 (Recovered)")
                    self.is_available = True

            except Exception as e:
                # ping 或恢复路径上的任意异常均不得顶掉后台任务
                if self.is_available:
                    logger.error("❌ [Cache] Redis 连接丢失，启用降级模式: %s", e)
                    self.is_available = False

    def get(self, key: str) -> Optional[str]:
        """安全获取：Redis 优先，其次内存；永不向调用方抛出 Redis 连接错误"""
        if self.is_available and self.redis_client is not None:
            try:
                val = self.redis_client.get(key)
                if val is not None:
                    return val
            except redis.RedisError as e:
                self._degrade_to_memory_only("get", e)
            except Exception as e:
                logger.warning("⚠️ [Cache] Get failed (non-RedisError): %s", e)
                self._degrade_to_memory_only("get", e)
        return self._memory_get(key)

    def setex(self, key: str, ttl: int, value: str) -> bool:
        """安全写入：Redis 可用则写 Redis；否则或失败后写入内存并返回 True"""
        if self.is_available and self.redis_client is not None:
            try:
                self.redis_client.setex(key, ttl, value)
                return True
            except redis.RedisError as e:
                self._degrade_to_memory_only("setex", e)
            except Exception as e:
                logger.warning("⚠️ [Cache] Setex failed (non-RedisError): %s", e)
                self._degrade_to_memory_only("setex", e)
        return self._memory_setex(key, ttl, value)

    def exists(self, key: str) -> int:
        """与 redis.exists 语义对齐：1 存在，0 不存在（便于 if not cache.exists）"""
        if self.is_available and self.redis_client is not None:
            try:
                if self.redis_client.exists(key):
                    return 1
            except redis.RedisError as e:
                self._degrade_to_memory_only("exists", e)
            except Exception as e:
                logger.warning("⚠️ [Cache] Exists failed (non-RedisError): %s", e)
                self._degrade_to_memory_only("exists", e)
        return 1 if self._memory_get(key) is not None else 0

    def delete(self, key: str) -> None:
        """删除键：内存与 Redis 侧同时尽力删除，不向调用方抛出连接错误"""
        self._memory_delete(key)
        if self.redis_client is not None and self.is_available:
            try:
                self.redis_client.delete(key)
            except redis.RedisError as e:
                self._degrade_to_memory_only("delete", e)
            except Exception as e:
                logger.warning("⚠️ [Cache] Delete failed (non-RedisError): %s", e)
                self._degrade_to_memory_only("delete", e)
