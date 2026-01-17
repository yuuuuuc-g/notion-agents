from unittest.mock import AsyncMock, patch

# ----
# Helpers for mocking


async def mock_astream_events(*args, **kwargs):
    yield {
        "event": "on_chat_model_stream",
        "data": {"chunk": AsyncMock(content="Hello from AI")},
    }


# ----
# Health check (connectivity) tests


def test_health_connectivity(test_client):
    """Basic connectivity: /health should return 200 and contain a version key"""
    response = test_client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert "version" in payload


def test_csrf_token_connectivity(test_client):
    """Basic connectivity: /csrf-token should return 200 and a csrf_token"""
    response = test_client.get("/csrf-token")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "csrf_token" in data


# ----
# /chat endpoint (DI & auth) tests


def test_chat_requires_auth(test_client):
    """Should return 401 if no Authorization header"""
    valid_payload = {
        "query": "Test query",
        "thread_id": "foo",
        "model_name": "bar/foobar",
    }
    response = test_client.post("/chat", json=valid_payload)
    assert response.status_code in [401, 403]


def test_chat_with_auth_and_mock_graph(test_client, auth_headers):
    """Should accept POST /chat and stream events, when graph is mocked via DI"""
    valid_payload = {
        "query": "Who is Socrates?",
        "thread_id": "test_123",
        "model_name": "deepseek/deepseek-chat",
    }
    with patch("server.graph.astream_events", side_effect=mock_astream_events):
        response = test_client.post("/chat", json=valid_payload, headers=auth_headers)
        assert response.status_code == 200
        assert "Hello from AI" in response.text
