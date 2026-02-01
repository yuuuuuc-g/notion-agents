"""
tests/services/test_search_session_manager.py
SearchSessionManager 完整测试 - 覆盖 Redis 和内存模式
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from services.search_session_manager import (
    SearchSessionManager,
    get_search_session_manager,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """Mock Redis 客户端"""
    mock = MagicMock()
    mock.hmset = MagicMock(return_value=True)
    mock.expire = MagicMock(return_value=True)
    mock.exists = MagicMock(return_value=1)
    mock.hgetall = MagicMock(return_value={})
    mock.delete = MagicMock(return_value=1)
    mock.keys = MagicMock(return_value=[])
    return mock


@pytest.fixture
def sample_search_results():
    """示例搜索结果"""
    return [
        {"title": "Python 基础", "content": "...", "score": 0.9},
        {"title": "Python 进阶", "content": "...", "score": 0.8},
    ]


@pytest.fixture
def sample_topics():
    """示例主题"""
    return [
        {"name": "基础语法", "count": 5},
        {"name": "数据分析", "count": 3},
    ]


# =============================================================================
# 初始化测试
# =============================================================================


def test_init_with_redis(mock_redis):
    """测试使用 Redis 初始化"""
    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    assert manager.redis == mock_redis
    assert manager.ttl == 300
    assert not hasattr(manager, "_memory_store")


def test_init_without_redis():
    """测试不使用 Redis 初始化（内存模式）"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    assert manager.redis is None
    assert manager.ttl == 300
    assert hasattr(manager, "_memory_store")
    assert manager._memory_store == {}


def test_init_default_ttl():
    """测试默认 TTL"""
    manager = SearchSessionManager()

    assert manager.ttl == 300


# =============================================================================
# create_session 测试
# =============================================================================


@pytest.mark.asyncio
async def test_create_session_redis(mock_redis, sample_search_results, sample_topics):
    """测试在 Redis 模式下创建会话"""
    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    session_id = await manager.create_session(
        query="test query", search_results=sample_search_results, topics=sample_topics
    )

    # 验证返回的 session_id 格式
    assert session_id.startswith("search_session:")

    # 验证调用了 Redis
    assert mock_redis.hmset.called
    assert mock_redis.expire.called

    # 验证调用参数
    call_args = mock_redis.hmset.call_args[0]
    assert call_args[0] == session_id  # session_id

    session_data = call_args[1]
    assert session_data["query"] == "test query"
    assert json.loads(session_data["search_results"]) == sample_search_results
    assert json.loads(session_data["topics_detected"]) == sample_topics


@pytest.mark.asyncio
async def test_create_session_memory(sample_search_results, sample_topics):
    """测试在内存模式下创建会话"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    session_id = await manager.create_session(
        query="test query", search_results=sample_search_results, topics=sample_topics
    )

    # 验证会话被存储在内存中
    assert session_id in manager._memory_store

    session_data = manager._memory_store[session_id]
    assert session_data["query"] == "test query"
    assert json.loads(session_data["search_results"]) == sample_search_results
    assert json.loads(session_data["topics_detected"]) == sample_topics


@pytest.mark.asyncio
async def test_create_session_redis_error(mock_redis):
    """测试 Redis 创建会话时的错误处理"""
    mock_redis.hmset.side_effect = Exception("Redis error")

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    with pytest.raises(Exception, match="Redis error"):
        await manager.create_session(query="test", search_results=[], topics=[])


# =============================================================================
# get_session 测试
# =============================================================================


@pytest.mark.asyncio
async def test_get_session_redis_success(mock_redis):
    """测试从 Redis 获取会话成功"""
    # Mock Redis 返回数据
    mock_redis.exists.return_value = 1
    mock_redis.hgetall.return_value = {
        b"query": b"test query",
        b"search_results": b'[{"title": "test"}]',
        b"topics_detected": b'[{"name": "topic1"}]',
        b"created_at": b"1234567890.0",
        b"expires_at": b"1234567890.0",
    }

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    session = await manager.get_session("search_session:test-id")

    # 验证返回的数据
    assert session is not None
    assert session["query"] == "test query"
    assert session["search_results"] == [{"title": "test"}]
    assert session["topics_detected"] == [{"name": "topic1"}]
    assert isinstance(session["created_at"], float)
    assert isinstance(session["expires_at"], float)


@pytest.mark.asyncio
async def test_get_session_redis_not_found(mock_redis):
    """测试 Redis 中会话不存在"""
    mock_redis.exists.return_value = 0

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    session = await manager.get_session("search_session:not-exist")

    assert session is None


@pytest.mark.asyncio
async def test_get_session_memory_success(sample_search_results, sample_topics):
    """测试从内存获取会话成功"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    # 创建会话
    session_id = await manager.create_session(
        query="test query", search_results=sample_search_results, topics=sample_topics
    )

    # 获取会话
    session = await manager.get_session(session_id)

    assert session is not None
    assert session["query"] == "test query"
    assert session["search_results"] == sample_search_results
    assert session["topics_detected"] == sample_topics


@pytest.mark.asyncio
async def test_get_session_memory_not_found():
    """测试内存中会话不存在"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    session = await manager.get_session("search_session:not-exist")

    assert session is None


@pytest.mark.asyncio
async def test_get_session_memory_expired():
    """测试内存中会话已过期"""
    manager = SearchSessionManager(redis_client=None, ttl=1)

    # 创建会话
    session_id = await manager.create_session(
        query="test", search_results=[], topics=[]
    )

    # 等待过期
    await asyncio.sleep(1.1)

    # 获取会话（应该返回 None）
    session = await manager.get_session(session_id)

    assert session is None
    # 验证会话已被删除
    assert session_id not in manager._memory_store


@pytest.mark.asyncio
async def test_get_session_redis_error(mock_redis):
    """测试 Redis 获取会话时的错误处理"""
    mock_redis.exists.side_effect = Exception("Redis error")

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    session = await manager.get_session("search_session:test")

    assert session is None


@pytest.mark.asyncio
async def test_get_session_decode_bytes():
    """测试解码 Redis 返回的 bytes 数据"""
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 1

    # Redis 返回 bytes 格式的数据
    mock_redis.hgetall.return_value = {
        b"query": b"test query",
        b"search_results": b"[]",
        b"topics_detected": b"[]",
        b"created_at": b"1234567890.0",
        b"expires_at": b"1234567890.0",
    }

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    session = await manager.get_session("search_session:test")

    # 验证数据被正确解码
    assert session is not None
    assert session["query"] == "test query"


@pytest.mark.asyncio
async def test_get_session_decode_strings():
    """测试处理 Redis 返回的 string 数据"""
    mock_redis = MagicMock()
    mock_redis.exists.return_value = 1

    # Redis 返回 string 格式的数据（某些 Redis 客户端配置）
    mock_redis.hgetall.return_value = {
        "query": "test query",
        "search_results": "[]",
        "topics_detected": "[]",
        "created_at": "1234567890.0",
        "expires_at": "1234567890.0",
    }

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    session = await manager.get_session("search_session:test")

    # 验证数据被正确处理
    assert session is not None
    assert session["query"] == "test query"


# =============================================================================
# delete_session 测试
# =============================================================================


@pytest.mark.asyncio
async def test_delete_session_redis_success(mock_redis):
    """测试从 Redis 删除会话成功"""
    mock_redis.delete.return_value = 1

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    result = await manager.delete_session("search_session:test")

    assert result is True
    mock_redis.delete.assert_called_once_with("search_session:test")


@pytest.mark.asyncio
async def test_delete_session_redis_not_found(mock_redis):
    """测试 Redis 中会话不存在（删除失败）"""
    mock_redis.delete.return_value = 0

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    result = await manager.delete_session("search_session:not-exist")

    assert result is False


@pytest.mark.asyncio
async def test_delete_session_memory_success():
    """测试从内存删除会话成功"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    # 创建会话
    session_id = await manager.create_session(
        query="test", search_results=[], topics=[]
    )

    # 删除会话
    result = await manager.delete_session(session_id)

    assert result is True
    assert session_id not in manager._memory_store


@pytest.mark.asyncio
async def test_delete_session_memory_not_found():
    """测试内存中会话不存在（删除失败）"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    result = await manager.delete_session("search_session:not-exist")

    assert result is False


@pytest.mark.asyncio
async def test_delete_session_redis_error(mock_redis):
    """测试 Redis 删除会话时的错误处理"""
    mock_redis.delete.side_effect = Exception("Redis error")

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    result = await manager.delete_session("search_session:test")

    assert result is False


# =============================================================================
# cleanup_expired_sessions 测试
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_expired_sessions_redis():
    """测试 Redis 模式下清理过期会话（应该返回 0）"""
    mock_redis = MagicMock()
    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    count = await manager.cleanup_expired_sessions()

    # Redis 自动过期，不需要手动清理
    assert count == 0


@pytest.mark.asyncio
async def test_cleanup_expired_sessions_memory():
    """测试内存模式下清理过期会话"""
    manager = SearchSessionManager(redis_client=None, ttl=1)

    # 创建多个会话
    # session_id1 = await manager.create_session("test1", [], [])
    # session_id2 = await manager.create_session("test2", [], [])
    # session_id3 = await manager.create_session("test3", [], [])

    # 等待过期
    await asyncio.sleep(1.1)

    # 清理过期会话
    count = await manager.cleanup_expired_sessions()

    assert count == 3
    assert len(manager._memory_store) == 0


@pytest.mark.asyncio
async def test_cleanup_expired_sessions_memory_partial():
    """测试内存模式下部分会话过期"""
    manager = SearchSessionManager(redis_client=None, ttl=2)

    # 创建第一批会话
    session_id1 = await manager.create_session("test1", [], [])

    # 等待 1 秒
    await asyncio.sleep(1.1)

    # 创建第二批会话
    session_id2 = await manager.create_session("test2", [], [])

    # 再等待 1 秒（此时第一批过期，第二批未过期）
    await asyncio.sleep(1.1)

    # 清理过期会话
    count = await manager.cleanup_expired_sessions()

    assert count == 1
    assert session_id1 not in manager._memory_store
    assert session_id2 in manager._memory_store


# =============================================================================
# get_stats 测试
# =============================================================================


@pytest.mark.asyncio
async def test_get_stats_redis(mock_redis):
    """测试 Redis 模式下获取统计信息"""
    mock_redis.keys.return_value = [b"session1", b"session2", b"session3"]

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    stats = await manager.get_stats()

    assert stats["active_sessions"] == 3
    assert stats["ttl"] == 300
    assert stats["storage_mode"] == "redis"

    mock_redis.keys.assert_called_once_with("search_session:*")


@pytest.mark.asyncio
async def test_get_stats_redis_error(mock_redis):
    """测试 Redis 获取统计信息时的错误处理"""
    mock_redis.keys.side_effect = Exception("Redis error")

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    stats = await manager.get_stats()

    assert stats["active_sessions"] == -1
    assert stats["storage_mode"] == "redis"


@pytest.mark.asyncio
async def test_get_stats_memory():
    """测试内存模式下获取统计信息"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    # 创建几个会话
    await manager.create_session("test1", [], [])
    await manager.create_session("test2", [], [])

    stats = await manager.get_stats()

    assert stats["active_sessions"] == 2
    assert stats["ttl"] == 300
    assert stats["storage_mode"] == "memory"


# =============================================================================
# get_search_session_manager 测试
# =============================================================================


def test_get_search_session_manager_singleton():
    """测试全局单例"""
    # 重置全局变量
    import services.search_session_manager as ssm

    ssm.search_session_manager = None

    with patch("core.container.container") as mock_container:
        mock_redis = MagicMock()
        mock_container.redis_client.return_value = mock_redis

        # 第一次调用
        manager1 = get_search_session_manager()

        # 第二次调用（应该返回同一个实例）
        manager2 = get_search_session_manager()

        assert manager1 is manager2


def test_get_search_session_manager_fallback():
    """测试无法获取 Redis 时的降级"""
    # 重置全局变量
    import services.search_session_manager as ssm

    ssm.search_session_manager = None

    with patch("core.container.container") as mock_container:
        # 模拟获取 Redis 失败
        mock_container.redis_client.side_effect = Exception("Cannot get Redis")

        manager = get_search_session_manager()

        # 应该使用内存模式
        assert manager.redis is None
        assert hasattr(manager, "_memory_store")


# =============================================================================
# 集成测试
# =============================================================================


@pytest.mark.asyncio
async def test_full_workflow_redis(mock_redis):
    """测试完整的 Redis 工作流程"""
    # Mock Redis 返回数据
    created_session_id = None

    def mock_hmset(sid, data):
        nonlocal created_session_id
        created_session_id = sid
        return True

    def mock_hgetall(sid):
        if sid == created_session_id:
            return {
                b"query": b"test query",
                b"search_results": b'[{"title": "test"}]',
                b"topics_detected": b'[{"name": "topic1"}]',
                b"created_at": b"1234567890.0",
                b"expires_at": b"9999999999.0",  # 不会过期
            }
        return {}

    mock_redis.hmset.side_effect = mock_hmset
    mock_redis.hgetall.side_effect = mock_hgetall
    mock_redis.exists.return_value = 1

    manager = SearchSessionManager(redis_client=mock_redis, ttl=300)

    # 1. 创建会话
    session_id = await manager.create_session(
        query="test query",
        search_results=[{"title": "test"}],
        topics=[{"name": "topic1"}],
    )

    assert session_id.startswith("search_session:")

    # 2. 获取会话
    session = await manager.get_session(session_id)

    assert session is not None
    assert session["query"] == "test query"

    # 3. 删除会话
    result = await manager.delete_session(session_id)

    assert result is True


@pytest.mark.asyncio
async def test_full_workflow_memory():
    """测试完整的内存工作流程"""
    manager = SearchSessionManager(redis_client=None, ttl=300)

    # 1. 创建会话
    session_id = await manager.create_session(
        query="test query",
        search_results=[{"title": "test"}],
        topics=[{"name": "topic1"}],
    )

    # 2. 获取会话
    session = await manager.get_session(session_id)

    assert session is not None
    assert session["query"] == "test query"

    # 3. 获取统计
    stats = await manager.get_stats()

    assert stats["active_sessions"] == 1

    # 4. 删除会话
    result = await manager.delete_session(session_id)

    assert result is True

    # 5. 再次获取统计
    stats = await manager.get_stats()

    assert stats["active_sessions"] == 0


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=services.search_session_manager",
            "--cov-report=term-missing",
        ]
    )
