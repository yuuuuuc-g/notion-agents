"""
redis_client.py
Redis 连接池单例模式 (修复 SSL 参数 bug)
功能：
1. 动态构建连接参数，防止传递不支持的 SSL 参数
2. 统一管理 Redis 连接
"""
import logging
from typing import Optional

import redis

from config.settings import SETTINGS

# 获取日志记录器
logger = logging.getLogger(__name__)


class RedisClient:
    _instance: Optional[redis.Redis] = None
    _pool: Optional[redis.ConnectionPool] = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        """
        获取 Redis 连接单例 (Lazy Loading)
        """
        if cls._instance is None:
            try:
                logger.info(
                    f"🔌 Connecting to Redis at {SETTINGS.REDIS_HOST}:{SETTINGS.REDIS_PORT}..."
                )

                # 1. 动态构建参数字典
                pool_kwargs = {
                    "host": SETTINGS.REDIS_HOST,
                    "port": SETTINGS.REDIS_PORT,
                    "password": SETTINGS.REDIS_PASSWORD,
                    "db": SETTINGS.REDIS_DB,
                    "decode_responses": True,  # 自动转码
                    "socket_timeout": 5,
                    "max_connections": SETTINGS.REDIS_MAX_CONNECTIONS,
                }

                # ⚠️ 只有明确开启 SSL 时才加入该参数
                if SETTINGS.REDIS_SSL:
                    pool_kwargs["ssl"] = True

                # 2. 建立连接池
                cls._pool = redis.ConnectionPool(**pool_kwargs)

                # 3. 从池中获取客户端
                cls._instance = redis.Redis(connection_pool=cls._pool)

                # 4. 立即测试连接
                cls._instance.ping()
                logger.info("✅ Redis connection established successfully.")

            except redis.ConnectionError as e:
                logger.critical(f"❌ Redis connection failed: {e}")
                raise e
            except TypeError as e:
                logger.critical(f"❌ Redis configuration error: {e}")
                raise e
            except Exception as e:
                logger.error(f"❌ Unexpected Redis error: {e}")
                raise e

        return cls._instance

    @classmethod
    def close(cls):
        """优雅关闭"""
        if cls._instance:
            try:
                cls._instance.close()
                logger.info("🔒 Redis connection closed.")
            except Exception as e:  # ✅ 修复：虽然 close 很少抛错，但加上 Exception 更规范
                logger.warning(f"Error closing Redis connection: {e}")

        if cls._pool:
            try:
                cls._pool.disconnect()
            except Exception:  # ✅ 修复：这里就是之前裸露 except: 的地方
                pass
            logger.info("🔒 Redis connection pool disconnected.")
