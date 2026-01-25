# 修正 URL: /api/health, /api/csrf-token
# 修正断言: 访问 /api/health 应返回 "ok"
def test_health_connectivity(client, mock_container):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"  # api/routes/system.py 返回的是 ok
    assert payload["redis"] in ["connected", "error"]


def test_csrf_token_connectivity(client):
    response = client.get("/api/csrf-token")
    assert response.status_code == 200
    assert "csrf_token" in response.json()
