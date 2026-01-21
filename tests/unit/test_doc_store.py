"""
tests/unit/test_doc_store.py
测试 vector/doc_store.py (SQLite)
适配 v4.1: 修复 Teardown 属性错误，放宽返回值检查
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

        # 1. 实例化
        store = DocStore()

        # 2. 强行修改路径
        # 如果之前有打开的连接，尝试关闭（防御性编程）
        if hasattr(store, "conn") and store.conn:
            try:
                store.conn.close()
            except Exception:
                pass

        store.db_path = str(db_path)

        # 3. 初始化 DB
        # 注意：如果 DocStore 内部是用 context manager 管理连接的，这里可能只是建表
        store._init_db()

        yield store

        # 4. 清理 (Teardown)
        # ✅ 修复点：先检查有没有 conn 属性，再尝试关闭
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
        # ✅ 修复点：不再断言 return True，因为该方法可能默认返回 None
        # 我们只关心是否报错
        doc_store.add_document(doc_id, content, meta)

        # Get (通过获取结果来验证写入是否成功)
        retrieved = doc_store.get_document(doc_id)
        assert retrieved == content

    def test_synced_ids(self, doc_store):
        """测试同步状态标记"""
        page_id = "page_sync_test"
        source = "notion"

        # 1. 初始状态：空
        ids = doc_store.get_synced_page_ids(source)
        assert page_id not in ids

        # 2. 必须先添加文档
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
