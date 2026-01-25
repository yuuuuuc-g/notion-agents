"""
tests/unit/test_doc_store.py
测试 vector/doc_store.py (SQLite)
适配 v4.2: 修复方法名变更 (_init_db -> _ensure_integrity_and_init)
"""

import pytest

from vector.doc_store import DocStore


class TestDocStore:
    @pytest.fixture
    def doc_store(self, tmp_path):
        """
        创建一个基于临时文件的 DocStore 实例
        """
        # 使用临时文件路径
        db_path = tmp_path / "test_doc_store.db"

        # 1. 实例化 (此时它会连接到默认的生产库)
        store = DocStore()

        # 2. 强行断开默认连接 (Hack)
        if hasattr(store, "conn") and store.conn:
            try:
                store.conn.close()
            except Exception:
                pass

        # 3. 指向新的临时文件
        store.db_path = str(db_path)

        # 4. 🔥 修复点：调用新的初始化方法 (原 _init_db 已废弃)
        # 这会自动创建连接、检查完整性并建表
        store._ensure_integrity_and_init()

        yield store

        # 5. 清理 (Teardown)
        if hasattr(store, "conn") and store.conn:
            try:
                store.conn.close()
            except Exception:
                pass

    def test_add_and_get_document(self, doc_store):
        """测试基础的增查功能"""
        doc_id = "doc_1"
        content = "Test Content"
        meta = {"author": "me"}

        # Add
        # 这里的返回值取决于具体实现，我们关注副作用(Side Effect)
        doc_store.add_document(doc_id, content, meta)

        # Get
        retrieved = doc_store.get_document(doc_id)
        assert retrieved == content

    def test_synced_ids(self, doc_store):
        """测试同步状态标记"""
        page_id = "page_sync_test"
        source = "notion"

        # 1. 初始状态：空
        ids = doc_store.get_synced_page_ids(source)
        assert page_id not in ids

        # 2. 先添加文档 (模拟真实流程)
        doc_store.add_document(page_id, "Some content", {"title": "Test"})

        # 3. 标记同步
        doc_store.mark_page_synced(page_id, source)

        # 4. 验证
        ids = doc_store.get_synced_page_ids(source)
        assert page_id in ids

    def test_update_sync_time(self, doc_store):
        """测试更新时间戳"""
        try:
            doc_store.update_last_full_sync_time()
            assert True
        except Exception as e:
            pytest.fail(f"update_last_full_sync_time raised exception: {e}")
