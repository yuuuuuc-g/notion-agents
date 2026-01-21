"""
vector/doc_store.py
[Level-Chunk Upgrade + Disaster Recovery]
父文档存储仓库 (基于 SQLite)
已包含功能:
1. 线程安全连接 (_get_conn)
2. WAL 模式与完整表结构
3. ✅ 新增: 启动时自动检查数据库完整性，损坏自动修复 (Backup & Rebuild)
4. ✅ 新增: 规范化 Logger
"""
import json
import logging
import os
import shutil
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings import SETTINGS

logger = logging.getLogger(__name__)


class DocStore:
    def __init__(self, db_name="doc_store.db"):
        self.db_path = os.path.join(SETTINGS.PROJECT_ROOT, db_name)
        # 🛡️ 启动时进行完整性检查，如果损坏则重置
        self._ensure_integrity_and_init()

    def _get_conn(self):
        """
        获取数据库连接
        - timeout=30: 防止并发锁死
        - check_same_thread=False: 允许 FastAPI 多线程调用
        """
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def _ensure_integrity_and_init(self):
        """
        安全初始化：检查损坏并自动重建
        """
        try:
            # 1. 尝试连接并执行完整性检查
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
                if result and result[0] != "ok":
                    raise sqlite3.DatabaseError(f"Integrity check failed: {result}")

                # 2. 如果检查通过，初始化表结构
                self._init_schema(conn)

        except sqlite3.DatabaseError as e:
            logger.error(f"❌ [DocStore] Database corrupted: {e}")
            self._handle_corruption()
            # 3. 修复后再次尝试初始化
            try:
                with self._get_conn() as conn:
                    self._init_schema(conn)
            except Exception as retry_e:
                logger.critical(
                    f"❌ [DocStore] Failed to re-init DB after recovery: {retry_e}"
                )
                raise retry_e

    def _handle_corruption(self):
        """处理损坏文件：备份 -> 删除"""
        if os.path.exists(self.db_path):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{self.db_path}.corrupted.{timestamp}.bak"
            try:
                shutil.move(self.db_path, backup_path)
                logger.warning(
                    f"🧹 Corrupted database moved to {backup_path}. Creating a fresh one."
                )
            except Exception as e:
                logger.critical(f"❌ Failed to move corrupted DB: {e}")
                # 如果无法移动（例如被锁），尝试直接删除
                try:
                    os.remove(self.db_path)
                except Exception:
                    pass

    def _init_schema(self, conn):
        """初始化表结构 (保留你的原有设计)"""
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
        """🔍 获取所有已同步的页面 ID"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT doc_id FROM documents WHERE source = ?", (source,)
                )
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"❌ [DocStore] Get Synced IDs Error: {e}")
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
                # logger.info(f"✅ [DocStore] Marked synced: {doc_id[:8]}")
        except Exception as e:
            logger.error(f"❌ [DocStore] Mark Synced Error: {e}")

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
                logger.info("🕒 [DocStore] Global sync time updated.")
        except Exception as e:
            logger.error(f"❌ [DocStore] Update Sync Time Error: {e}")

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
                # logger.info(f"📚 [DocStore] Saved Parent Document: {doc_id[:8]}...")
        except Exception as e:
            logger.error(f"❌ [DocStore] Add Error: {e}")

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
            logger.error(f"❌ [DocStore] Read Error: {e}")
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
            logger.error(f"❌ [DocStore] Read Meta Error: {e}")
        return None


# 单例模式
DOC_STORE = DocStore()
