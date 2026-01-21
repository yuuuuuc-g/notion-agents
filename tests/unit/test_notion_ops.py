"""
tests/unit/test_notion_ops.py
Notion 服务单元测试
"""
from unittest.mock import MagicMock, patch

import pytest

from notion.notion_ops import NotionService


# Mock requests 和 notion_client
@pytest.fixture
def mock_deps():
    with patch("notion.notion_ops.Client") as mock_client:
        with patch("notion.notion_ops.requests") as mock_requests:
            yield mock_client, mock_requests


class TestNotionService:
    def test_init_success(self, mock_deps):
        service = NotionService(token="test-token", default_db_id="db-1")
        assert service.token == "test-token"
        assert service.default_db_id == "db-1"

    def test_init_missing_token(self):
        with pytest.raises(ValueError):
            NotionService(token="", default_db_id="db-1")

    def test_create_page(self, mock_deps):
        mock_client, _ = mock_deps
        service = NotionService(token="test", default_db_id="db-1")

        # Mock create return
        mock_client.return_value.pages.create.return_value = {"id": "page-123"}

        resp = service.create_page("Title", [{"type": "paragraph"}])
        assert resp["id"] == "page-123"

    def test_fetch_database_success(self, mock_deps):
        _, mock_requests = mock_deps
        service = NotionService(token="test", default_db_id="db-1")

        # Mock requests response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "id": "p1",
                    "properties": {
                        "Name": {
                            "type": "title",
                            "title": [{"plain_text": "Test Page"}],
                        }
                    },
                }
            ],
            "has_more": False,
        }
        mock_requests.post.return_value = mock_resp

        # Mock get_page_text to return something
        with patch.object(service, "get_page_text", return_value="Content"):
            results = service.fetch_database_content()
            assert len(results) == 1
            assert results[0]["title"] == "Test Page"
