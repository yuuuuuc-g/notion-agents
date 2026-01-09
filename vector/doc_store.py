"""
vector/doc_store.py
[Level-Chunk Upgrade]
父文档存储仓库 (基于 SQLite)
只负责存取大段文本 (Parent Documents)，不负责向量计算。
"""
import sqlite3
import os
import json
from typing import Optional
from config.settings import SETTINGS

class DocStore:
    def __init__(self, db_name="doc_store.db"):
        # 将数据库文件放在项目根目录
        self.db_path = os.path.join(SETTINGS.PROJECT_ROOT, db_name)
        self._init_db()

    def _init_db(self):
        """初始化 SQLite 表结构"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 创建一个简单的 Key-Value 表
        # doc_id: 父文档的 UUID
        # content: 父文档的完整文本
        # metadata: 额外的元数据 (JSON格式)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                content TEXT,
                metadata TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def add_document(self, doc_id: str, content: str, metadata: dict = None):
        """存入父文档"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        
        try:
            # 使用 REPLACE INTO，如果 ID 存在则覆盖 (Upsert)
            cursor.execute('''
                REPLACE INTO documents (doc_id, content, metadata)
                VALUES (?, ?, ?)
            ''', (doc_id, content, meta_json))
            conn.commit()
            print(f"📚 [DocStore] Saved Parent Document: {doc_id[:8]}...")
        except Exception as e:
            print(f"❌ [DocStore] Add Error: {e}")
        finally:
            conn.close()

    def get_document(self, doc_id: str) -> Optional[str]:
        """读取父文档内容"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT content FROM documents WHERE doc_id = ?', (doc_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row[0] # 返回 content 字段
        return None

    def get_full_doc_with_meta(self, doc_id: str):
        """读取内容+元数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT content, metadata FROM documents WHERE doc_id = ?', (doc_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "content": row[0],
                "metadata": json.loads(row[1]) if row[1] else {}
            }
        return None

# 单例模式
DOC_STORE = DocStore()