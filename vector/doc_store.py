"""
vector/doc_store.py
[Level-Chunk Upgrade]
父文档存储仓库 (基于 SQLite)
已修复: 线程锁死问题 (Database Locked)
"""
import json
import os
import sqlite3
from typing import Optional

from config.settings import SETTINGS


class DocStore:
    def __init__(self, db_name="doc_store.db"):
        self.db_path = os.path.join(SETTINGS.PROJECT_ROOT, db_name)
        self._init_db()

    def _get_conn(self):
        """
        获取数据库连接的统一入口
        核心修复 1: timeout=30 (等待 30 秒而不是立刻报错)
        核心修复 2: check_same_thread=False (允许在多线程环境使用连接，尽管我们每次都新建)
        """
        return sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)

    def _init_db(self):
        """初始化 SQLite 表结构 + 开启 WAL 模式"""
        # 使用 with 语法自动管理关闭，防止资源泄漏
        with self._get_conn() as conn:
            # 核心修复 3: 开启 WAL 模式 (Write-Ahead Logging)
            # 这允许同时进行读写操作，大幅减少锁冲突
            conn.execute("PRAGMA journal_mode=WAL;")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    content TEXT,
                    metadata TEXT
                )
            """
            )
            conn.commit()

    def add_document(self, doc_id: str, content: str, metadata: dict = None):
        """存入父文档 (Upsert)"""
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)

        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    REPLACE INTO documents (doc_id, content, metadata)
                    VALUES (?, ?, ?)
                """,
                    (doc_id, content, meta_json),
                )
                conn.commit()
                # 成功后打印日志
                print(f"📚 [DocStore] Saved Parent Document: {doc_id[:8]}...")
        except Exception as e:
            print(f"❌ [DocStore] Add Error: {e}")
            # 这里不需要 conn.close()，因为 with 语句会自动处理

    def get_document(self, doc_id: str) -> Optional[str]:
        """读取父文档内容"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT content FROM documents WHERE doc_id = ?", (doc_id,)
                )
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception as e:
            print(f"❌ [DocStore] Read Error: {e}")
        return None

    def get_full_doc_with_meta(self, doc_id: str):
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
