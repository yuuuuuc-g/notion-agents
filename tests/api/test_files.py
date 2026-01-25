"""
tests/api/test_files.py
测试文件上传与归档接口
"""


def test_upload_file_success(client, mock_container):
    # 模拟 Cache 写入成功
    mock_cache = mock_container.cache_wrapper()
    mock_cache.setex.return_value = True

    files = {"files": ("test.txt", b"content", "text/plain")}
    response = client.post("/api/upload", files=files)
    assert response.status_code == 200
    assert "file_id" in response.json()


def test_archive_requires_auth(client):
    response = client.post("/api/archive", json={"file_id": "123"})
    assert response.status_code in [401, 403]


def test_archive_endpoint(client, auth_headers, mock_container):
    # 关键修复：确保 cache.exists 返回 True，否则 API 会抛出 404
    mock_cache = mock_container.cache_wrapper()
    mock_cache.exists.return_value = True

    response = client.post(
        "/api/archive",
        json={"file_id": "test_id", "summary": "test"},
        headers=auth_headers,
    )

    # 如果这里依然 404，说明 mock_cache 没有正确注入
    # 或者是 API 路由地址不对 (已确认为 /api/archive)
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
