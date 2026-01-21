import pytest


@pytest.mark.api
def test_health_connectivity(test_client):
    """测试健康检查接口"""
    response = test_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    # 验证 Redis 状态 (在 conftest 中被 Mock 为 connected)
    assert "redis" in payload


@pytest.mark.api
def test_csrf_token_connectivity(test_client):
    """测试 CSRF Token 获取"""
    response = test_client.get("/csrf-token")
    assert response.status_code == 200
    data = response.json()
    assert "csrf_token" in data
