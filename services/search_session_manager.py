"""
services/search_session_manager.py
搜索会话管理器 - 管理对话式搜索的会话状态
修复版 v3: 使用 asyncio.to_thread 包装同步 Redis 调用，解决 TypeError
"""
import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


class SearchSessionManager:
    """搜索会话管理器"""

    def __init__(self, redis_client=None, ttl: int = 300):
        """
        初始化会话管理器
        """
        self.redis = redis_client
        self.ttl = ttl

        if self.redis is None:
            logger.warning(
                "⚠️ [SearchSession] No Redis client provided, using in-memory storage"
            )
            self._memory_store: Dict[str, Dict] = {}

        logger.info(f"✅ [SearchSession] Initialized (TTL: {ttl}s)")

    def _generate_session_id(self) -> str:
        """生成会话ID"""
        return f"search_session:{uuid.uuid4()}"

    async def create_session(
        self, query: str, search_results: List[Dict], topics: List[Dict]
    ) -> str:
        """创建搜索会话"""
        session_id = self._generate_session_id()

        # 构建会话数据
        session_data = {
            "query": query,
            "search_results": json.dumps(search_results, ensure_ascii=False),
            "topics_detected": json.dumps(topics, ensure_ascii=False),
            "created_at": str(time.time()),
            "expires_at": str(time.time() + self.ttl),
        }

        try:
            if self.redis:
                # 🔥 修复：使用 asyncio.to_thread 包装同步 Redis 调用
                # 这样不会阻塞 Event Loop，且解决了 await bool 的报错
                await asyncio.to_thread(self.redis.hmset, session_id, session_data)
                await asyncio.to_thread(self.redis.expire, session_id, self.ttl)
                logger.info(f"✅ [SearchSession] Created session: {session_id} (Redis)")
            else:
                self._memory_store[session_id] = session_data
                logger.info(f"✅ [SearchSession] Created session: {session_id} (Memory)")

            return session_id

        except Exception as e:
            logger.error(f"❌ [SearchSession] Failed to create session: {e}")
            raise

    async def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话数据"""
        try:
            if self.redis:
                # 🔥 修复：使用 asyncio.to_thread 包装 exists
                exists = await asyncio.to_thread(self.redis.exists, session_id)
                if not exists:
                    logger.warning(
                        f"⚠️ [SearchSession] Session not found: {session_id}"
                    )
                    return None

                # 🔥 修复：使用 asyncio.to_thread 包装 hgetall
                data = await asyncio.to_thread(self.redis.hgetall, session_id)
            else:
                data = self._memory_store.get(session_id)
                if not data:
                    logger.warning(
                        f"⚠️ [SearchSession] Session not found: {session_id}"
                    )
                    return None

                expires_at = float(data.get("expires_at", 0))
                if time.time() > expires_at:
                    logger.warning(f"⚠️ [SearchSession] Session expired: {session_id}")
                    del self._memory_store[session_id]
                    return None

            # 兼容处理 bytes key/value (Redis 默认返回 bytes)
            decoded_data = {}
            for k, v in data.items():
                # 如果是 bytes 则解码，如果是 str 则保持
                key = k.decode("utf-8") if isinstance(k, bytes) else k
                val = v.decode("utf-8") if isinstance(v, bytes) else v
                decoded_data[key] = val

            data = decoded_data

            # 解析数据
            session = {
                "query": data.get("query"),
                "search_results": json.loads(data.get("search_results", "[]")),
                "topics_detected": json.loads(data.get("topics_detected", "[]")),
                "created_at": float(data.get("created_at", 0)),
                "expires_at": float(data.get("expires_at", 0)),
            }

            logger.info(f"✅ [SearchSession] Retrieved session: {session_id}")
            return session

        except Exception as e:
            logger.error(f"❌ [SearchSession] Failed to get session: {e}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        try:
            if self.redis:
                # 🔥 修复：使用 asyncio.to_thread 包装 delete
                result = await asyncio.to_thread(self.redis.delete, session_id)
                success = result > 0
            else:
                if session_id in self._memory_store:
                    del self._memory_store[session_id]
                    success = True
                else:
                    success = False

            if success:
                logger.info(f"✅ [SearchSession] Deleted session: {session_id}")
            else:
                logger.warning(
                    f"⚠️ [SearchSession] Session not found for deletion: {session_id}"
                )

            return success

        except Exception as e:
            logger.error(f"❌ [SearchSession] Failed to delete session: {e}")
            return False

    async def cleanup_expired_sessions(self) -> int:
        """清理过期会话 (仅内存模式需要)"""
        if self.redis:
            # Redis 自动过期，无需手动清理
            return 0

        now = time.time()
        expired_sessions = []
        for session_id, data in self._memory_store.items():
            expires_at = float(data.get("expires_at", 0))
            if now > expires_at:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self._memory_store[session_id]

        if expired_sessions:
            logger.info(
                f"🧹 [SearchSession] Cleaned up {len(expired_sessions)} expired sessions"
            )

        return len(expired_sessions)

    async def get_stats(self) -> Dict:
        """获取统计信息"""
        if self.redis:
            try:
                # 🔥 修复：使用 asyncio.to_thread 包装 keys
                keys = await asyncio.to_thread(self.redis.keys, "search_session:*")
                active_count = len(keys)
            except Exception:
                active_count = -1
        else:
            active_count = len(self._memory_store)

        return {
            "active_sessions": active_count,
            "ttl": self.ttl,
            "storage_mode": "redis" if self.redis else "memory",
        }


# 延迟初始化 (在 container 中创建)
search_session_manager: Optional[SearchSessionManager] = None


def get_search_session_manager() -> SearchSessionManager:
    """获取全局会话管理器实例"""
    global search_session_manager

    if search_session_manager is None:
        try:
            from core.container import container

            redis_client = container.redis_client()
            search_session_manager = SearchSessionManager(redis_client=redis_client)
        except Exception:
            logger.warning(
                "⚠️ [SearchSession] Failed to get Redis, using memory storage"
            )
            search_session_manager = SearchSessionManager(redis_client=None)

    return search_session_manager


if __name__ == "__main__":

    async def test():
        mgr = SearchSessionManager(ttl=5)
        sid = await mgr.create_session("test", [], [])
        print(f"Session created: {sid}")
        print(await mgr.get_session(sid))

    asyncio.run(test())
