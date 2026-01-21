"""
tests/services/test_archive_service.py
归档服务测试 (Full Version)
适配架构：ArchiveService Class + DI
"""
from unittest.mock import MagicMock

import pytest

from services.archive_service import ArchiveService


class TestArchiveService:
    @pytest.fixture
    def archive_service(self):
        mock_cache = MagicMock()
        mock_vs = MagicMock()
        mock_notion = MagicMock()
        service = ArchiveService(mock_cache, mock_vs, mock_notion)
        return service, mock_cache, mock_vs, mock_notion

    @pytest.mark.asyncio
    async def test_archive_file_success(self, archive_service):
        service, mock_cache, mock_vs, mock_notion = archive_service

        # Happy Path
        mock_cache.get.return_value = "Content"
        mock_notion.create_page.return_value = {"id": "page-1"}
        mock_vs.add_memory.return_value = True

        result = await service.archive_session("file_1", "Summary", "thread_1")

        assert result["status"] == "success"
        assert result["notion_id"] == "page-1"
        assert result["vector_synced"] is True

    @pytest.mark.asyncio
    async def test_archive_file_not_found(self, archive_service):
        service, mock_cache, _, _ = archive_service

        # Redis Miss
        mock_cache.get.return_value = None

        with pytest.raises(ValueError) as exc:
            await service.archive_session("missing_file", "Sum", "t1")

        assert "not found" in str(exc.value)

    @pytest.mark.asyncio
    async def test_archive_cleanup(self, archive_service):
        service, mock_cache, _, mock_notion = archive_service

        mock_cache.get.return_value = "Content"
        mock_notion.create_page.return_value = {"id": "p1"}

        # 执行带清理的归档
        await service.archive_session("file_1", "Sum", "t1", cleanup=True)

        # 验证是否删除了缓存
        mock_cache.delete.assert_called_once_with("file_1")
