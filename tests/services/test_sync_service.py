"""
tests/services/test_sync_service_coverage.py
针对 SyncService 的高覆盖率测试
适配：基于 Simple Class Mock 进行动态方法替换
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.sync_service import SyncService


@pytest.mark.asyncio
async def test_process_single_page_retry_logic(mock_container):
    """测试单个页面同步的重试机制"""
    # 1. 获取 Fake 实例
    mock_notion = mock_container.notion_service()
    mock_vector = mock_container.vector_store()

    # 2. 🔥 关键修正：将 Fake 实例的方法替换为 MagicMock
    # 这样我们需要 side_effect 和 call_count 时才能生效
    mock_vector.add_memory = MagicMock(
        side_effect=[
            Exception("Network Error"),  # 第1次失败
            Exception("Timeout"),  # 第2次失败
            True,  # 第3次成功
        ]
    )

    service = SyncService(mock_notion, mock_vector)

    page_data = {"id": "page_1", "content": "test content", "title": "Test Page"}
    synced_ids = set()

    # 3. 执行
    # Patch asyncio.sleep 以加速测试
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await service._process_single_page(page_data, synced_ids, "Spanish")

    # 4. 验证
    assert result == "new"
    # 验证重试逻辑
    assert mock_vector.add_memory.call_count == 3


@pytest.mark.asyncio
async def test_process_single_page_failure(mock_container):
    """测试重试耗尽后的失败情况"""
    mock_notion = mock_container.notion_service()
    mock_vector = mock_container.vector_store()

    # 🔥 替换为总是失败的 Mock
    mock_vector.add_memory = MagicMock(side_effect=Exception("Fatal Error"))

    service = SyncService(mock_notion, mock_vector)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await service._process_single_page(
            {"id": "p1", "content": "c"}, set(), "Gen"
        )

    assert result == "failed"


@pytest.mark.asyncio
async def test_sync_database_empty(mock_container):
    """测试空数据库情况"""
    mock_notion = mock_container.notion_service()

    # 🔥 替换 fetch_database_content
    # 注意：sync_database 中使用了 asyncio.to_thread 运行此同步方法
    mock_notion.fetch_database_content = MagicMock(return_value=[])

    service = SyncService(mock_notion, mock_container.vector_store())

    result = await service.sync_database("db_id")
    assert result["synced_count"] == 0
    assert "No pages found" in result["message"]


@pytest.mark.asyncio
async def test_sync_database_concurrency(mock_container):
    """测试并发同步逻辑"""
    mock_notion = mock_container.notion_service()
    mock_vector = mock_container.vector_store()

    # 模拟返回 5 个页面
    pages = [{"id": f"p{i}", "content": "c", "title": f"t{i}"} for i in range(5)]

    # 🔥 替换方法以支持统计
    mock_notion.fetch_database_content = MagicMock(return_value=pages)
    mock_vector.add_memory = MagicMock(return_value=True)

    service = SyncService(mock_notion, mock_vector)

    # 执行同步
    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await service.sync_database("db_id")

    assert result["status"] == "success"
    assert result["synced_count"] == 5
    # 验证确实调用了 5 次写入
    assert mock_vector.add_memory.call_count == 5
