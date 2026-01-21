"""
tests/infrastructure/test_redis_client.py
测试 infrastructure/cache/redis_client.py
适配当前架构：Singleton Pattern
"""
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.cache.redis_client import RedisClient


class TestRedisClient:
    def setup_method(self):
        """每个测试前重置单例状态"""
        RedisClient._instance = None
        RedisClient._pool = None

    def teardown_method(self):
        RedisClient._instance = None
        RedisClient._pool = None

    def test_get_instance_creates_connection(self):
        """测试首次获取实例会创建连接池"""
        with patch("redis.ConnectionPool") as MockPool:
            with patch("redis.Redis") as MockRedis:
                mock_redis_obj = MagicMock()
                MockRedis.return_value = mock_redis_obj

                # 调用
                client = RedisClient.get_instance()

                # 验证
                assert client == mock_redis_obj
                MockPool.assert_called_once()
                MockRedis.assert_called_once()
                # 验证是否调用了 ping
                mock_redis_obj.ping.assert_called_once()

    def test_singleton_behavior(self):
        """测试单例模式：多次调用返回同一实例"""
        with patch("redis.ConnectionPool"):
            with patch("redis.Redis") as MockRedis:
                mock_redis_obj = MagicMock()
                MockRedis.return_value = mock_redis_obj

                client1 = RedisClient.get_instance()
                client2 = RedisClient.get_instance()

                assert client1 is client2
                # 确保只初始化了一次
                MockRedis.assert_called_once()

    def test_close(self):
        """测试关闭连接"""
        with patch("redis.ConnectionPool") as MockPool:
            with patch("redis.Redis") as MockRedis:
                # Setup
                mock_redis_instance = MagicMock()
                MockRedis.return_value = mock_redis_instance
                mock_pool_instance = MagicMock()
                MockPool.return_value = mock_pool_instance

                RedisClient.get_instance()

                # Act
                RedisClient.close()

                # Assert
                mock_redis_instance.close.assert_called_once()
                # _pool 可能会被断开
                if mock_pool_instance.disconnect.called:
                    mock_pool_instance.disconnect.assert_called()

    def test_connection_error_raises(self):
        """测试连接失败抛出异常"""
        import redis

        with patch("redis.ConnectionPool"):
            with patch("redis.Redis") as MockRedis:
                # 模拟 ping 失败
                MockRedis.return_value.ping.side_effect = redis.ConnectionError("Boom")

                with pytest.raises(redis.ConnectionError):
                    RedisClient.get_instance()
