"""
utils/cache_fallback.py
Redis 缓存降级包装器
功能：
1. 包装 Redis 操作 (get, setex, exists)，在 Redis 挂掉时不抛出异常
2. 提供后台健康检查，自动恢复连接状态
"""
import asyncio
import logging

import redis

logger = logging.getLogger(__name__)


class CacheWithFallback:
    """带熔断/降级机制的缓存包装器"""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.is_available = True
        self._check_task = None

    async def start_health_check(self):
        """
        后台任务：定期检查 Redis 健康状态
        """
        logger.info("💓 [Cache] 启动 Redis 健康检查...")
        while True:
            try:
                await asyncio.sleep(30)  # 每 30 秒检查一次

                # 尝试 Ping
                self.redis_client.ping()

                if not self.is_available:
                    logger.info("✅ [Cache] Redis 恢复可用 (Recovered)")
                    self.is_available = True

            except Exception as e:
                if self.is_available:
                    logger.error(f"❌ [Cache] Redis 连接丢失，启用降级模式: {e}")
                    self.is_available = False

    def get(self, key: str) -> str:
        """安全获取，失败返回 None"""
        if not self.is_available:
            return None

        try:
            return self.redis_client.get(key)
        except Exception as e:
            logger.warning(f"⚠️ [Cache] Get failed: {e}")
            self.is_available = False
            return None

    def setex(self, key: str, ttl: int, value: str) -> bool:
        """安全写入，失败返回 False"""
        if not self.is_available:
            return False

        try:
            self.redis_client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.warning(f"⚠️ [Cache] Setex failed: {e}")
            self.is_available = False
            return False

    def exists(self, key: str) -> bool:
        """安全检查存在性"""
        if not self.is_available:
            return False

        try:
            return self.redis_client.exists(key)
        except Exception as e:
            logger.warning(f"⚠️ [Cache] Exists check failed: {e}")
            self.is_available = False
            return False
