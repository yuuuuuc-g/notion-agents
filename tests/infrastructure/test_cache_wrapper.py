"""
tests/infrastructure/test_cache_wrapper.py
测试 utils/cache_fallback.py 中的 CacheWithFallback 类
适配当前架构：CacheWithFallback(redis_client)
✅ 优化版：增强异步健康检查的测试覆盖率 (多周期 + 异常韧性)
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from utils.cache_fallback import CacheWithFallback


class TestCacheWithFallback:
    @pytest.fixture
    def mock_redis(self):
        """创建一个模拟的 Redis 客户端"""
        m = MagicMock()
        m.ping.return_value = True
        return m

    @pytest.fixture
    def cache(self, mock_redis):
        """初始化 CacheWithFallback"""
        return CacheWithFallback(mock_redis)

    def test_initialization(self, cache):
        assert cache is not None
        assert cache.is_available is True

    # === 基础功能测试 (保持不变) ===

    def test_get_success(self, cache, mock_redis):
        mock_redis.get.return_value = "value"
        result = cache.get("key")
        assert result == "value"
        mock_redis.get.assert_called_with("key")

    def test_get_fallback(self, cache, mock_redis):
        """测试 Redis 报错时降级"""
        mock_redis.get.side_effect = Exception("Connection lost")

        # 第一次调用，捕获异常，标记不可用
        result = cache.get("key")
        assert result is None
        assert cache.is_available is False

        # 第二次调用，直接返回 None，不再调 Redis
        mock_redis.get.reset_mock()
        result2 = cache.get("key")
        assert result2 is None
        mock_redis.get.assert_not_called()

    def test_setex_success(self, cache, mock_redis):
        mock_redis.setex.return_value = True
        result = cache.setex("key", 60, "value")
        assert result is True
        mock_redis.setex.assert_called_with("key", 60, "value")

    def test_setex_fallback(self, cache, mock_redis):
        mock_redis.setex.side_effect = Exception("Error")
        result = cache.setex("key", 60, "val")
        assert result is False
        assert cache.is_available is False

    def test_exists_success(self, cache, mock_redis):
        mock_redis.exists.return_value = 1
        assert cache.exists("key") == 1

    def test_exists_fallback(self, cache, mock_redis):
        mock_redis.exists.side_effect = Exception("Error")
        assert cache.exists("key") is False
        assert cache.is_available is False

    # === 异步健康检查测试 (核心优化) ===

    @pytest.mark.asyncio
    async def test_health_check_recovery(self, cache, mock_redis):
        """测试：Redis 挂掉后，通过健康检查自动恢复"""
        cache.is_available = False  # 初始状态为挂掉
        mock_redis.ping.return_value = True  # Redis 其实好了

        # 模拟：第一次 sleep (让检查跑一次)，第二次 sleep (抛出取消异常退出循环)
        # 这样我们既验证了逻辑，又不会陷入死循环
        with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError()]):
            try:
                await cache.start_health_check()
            except asyncio.CancelledError:
                pass

        assert cache.is_available is True
        mock_redis.ping.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_multiple_cycles(self, cache, mock_redis):
        """测试：验证健康检查是否按预期循环执行多次"""
        mock_redis.ping.return_value = True

        # 模拟：sleep 3次 (对应3个检测周期)，第4次退出
        # 这模拟了任务在后台持续运行的过程
        with patch(
            "asyncio.sleep", side_effect=[None, None, None, asyncio.CancelledError()]
        ):
            try:
                await cache.start_health_check()
            except asyncio.CancelledError:
                pass

        # 验证 ping 被调用了至少3次，证明循环机制有效
        assert mock_redis.ping.call_count >= 3

    @pytest.mark.asyncio
    async def test_health_check_exception_resilience(self, cache, mock_redis):
        """
        测试：Ping 抛出异常时的韧性
        确保当 Redis 连接真的断开（ping 抛错）时，后台任务不会崩溃退出，
        而是能继续运行，直到 Redis 恢复。
        """
        # 设置 ping 的行为序列：
        # 1. Exception (Redis 挂了)
        # 2. Exception (Redis 还没好)
        # 3. True (Redis 好了)
        mock_redis.ping.side_effect = [
            Exception("Timeout"),
            Exception("Connection Refused"),
            True,
        ]

        # 初始状态是好的
        cache.is_available = True

        # 模拟3次循环后退出
        with patch(
            "asyncio.sleep", side_effect=[None, None, None, asyncio.CancelledError()]
        ):
            try:
                await cache.start_health_check()
            except asyncio.CancelledError:
                pass

        # 验证逻辑：
        # 1. 任务没有因为 Exception 而 Crash (如果 Crash，测试会在第1或2次就停止)
        # 2. 最终状态应该是 True（因为最后一次 ping 成功了）
        # 3. 中间状态变更（虽然只能测最终结果，但 ping 调用次数证明了过程）
        assert cache.is_available is True
        assert mock_redis.ping.call_count >= 3
