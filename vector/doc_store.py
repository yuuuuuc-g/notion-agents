"""
vector/doc_store.py
[Level-Chunk Upgrade]
父文档存储仓库 (基于 SQLite)
已修复: 线程锁死、增量同步接口缺失、同步时间更新接口缺失
"""
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from config.settings import SETTINGS


class DocStore:
    def __init__(self, db_name="doc_store.db"):
        self.db_path = os.path.join(SETTINGS.PROJECT_ROOT, db_name)
        self._init_db()

    def _get_conn(self):
        """获取数据库连接，开启超时等待和多线程支持"""
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def _init_db(self):
        """初始化表结构：增加同步状态支持"""
        with self._get_conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            # 1. 核心表：存储内容与元数据
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    content TEXT,
                    metadata TEXT,
                    source TEXT,
                    last_synced_at REAL
                )
                """
            )
            # 2. 系统信息表：存储最后同步时间等全局状态
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.commit()

    def get_synced_page_ids(self, source: str = "notion") -> List[str]:
        """🔍 获取所有已同步的页面 ID (用于增量同步判定)"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT doc_id FROM documents WHERE source = ?", (source,)
                )
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            print(f"❌ [DocStore] Get Synced IDs Error: {e}")
            return []

    def mark_page_synced(self, doc_id: str, source: str = "notion"):
        """✅ 标记页面为已同步状态"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE documents SET source = ?, last_synced_at = ? WHERE doc_id = ?",
                    (source, time.time(), doc_id),
                )
                conn.commit()
                print(f"✅ [DocStore] Marked synced: {doc_id[:8]}")
        except Exception as e:
            print(f"❌ [DocStore] Mark Synced Error: {e}")

    def update_last_full_sync_time(self, key: str = "last_notion_sync"):
        """🕒 记录最后一次全量同步完成的时间点"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO system_config (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, str(time.time())),
                )
                conn.commit()
                print("🕒 [DocStore] Global sync time updated.")
        except Exception as e:
            print(f"❌ [DocStore] Update Sync Time Error: {e}")

    def add_document(
        self, doc_id: str, content: str, metadata: dict = None, source: str = "notion"
    ):
        """存入父文档 (Upsert)"""
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO documents (doc_id, content, metadata, source, last_synced_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(doc_id) DO UPDATE SET
                        content=excluded.content,
                        metadata=excluded.metadata,
                        source=excluded.source,
                        last_synced_at=excluded.last_synced_at
                    """,
                    (doc_id, content, meta_json, source, time.time()),
                )
                conn.commit()
                print(f"📚 [DocStore] Saved Parent Document: {doc_id[:8]}...")
        except Exception as e:
            print(f"❌ [DocStore] Add Error: {e}")

    def get_document(self, doc_id: str) -> Optional[str]:
        """读取父文档内容"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content FROM documents WHERE doc_id = ?", (doc_id,)
                )
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            print(f"❌ [DocStore] Read Error: {e}")
        return None

    def get_full_doc_with_meta(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """读取内容+元数据"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content, metadata FROM documents WHERE doc_id = ?",
                    (doc_id,),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "content": row[0],
                        "metadata": json.loads(row[1]) if row[1] else {},
                    }
        except Exception as e:
            print(f"❌ [DocStore] Read Meta Error: {e}")
        return None


# 单例模式
DOC_STORE = DocStore()
