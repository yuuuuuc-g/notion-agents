"""
tests/api/test_files.py
测试文件上传与归档接口
"""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.api
def test_upload_file_success(test_client):
    """测试文件上传流程"""
    file_content = b"This is a test file content."
    files = {"files": ("test_doc.txt", file_content, "text/plain")}

    # Mock 解析服务
    with patch(
        "api.routes.files.extract_text_from_upload_file", new_callable=AsyncMock
    ) as mock_extract:
        mock_extract.return_value = "Parsed text content"

        response = test_client.post("/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "file_id" in data


@pytest.mark.api
def test_archive_requires_auth(test_client):
    """测试归档接口鉴权"""
    payload = {
        "file_id": "session_123",
        "summary": "test summary",
        "thread_id": "thread_1",
    }
    response = test_client.post("/archive", json=payload)
    assert response.status_code in [401, 403]


@pytest.mark.api
def test_archive_endpoint(test_client, auth_headers, mock_cache_wrapper):
    """
    测试归档接口
    """
    payload = {"file_id": "sess_123", "summary": "sum", "thread_id": "th_1"}

    # ✅ 修复点：先清除 side_effect，确保 return_value 生效
    mock_cache_wrapper.exists.side_effect = None
    mock_cache_wrapper.exists.return_value = True

    # Mock 后台任务中的 Service 调用
    with patch("services.archive_service.ArchiveService.archive_session"):
        response = test_client.post("/archive", json=payload, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "queued"
