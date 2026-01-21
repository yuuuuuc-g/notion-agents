from unittest.mock import patch

import pytest

from tests.utils import mock_astream_events_generator


@pytest.mark.api
def test_chat_requires_auth(test_client):
    """测试未授权访问拦截"""
    payload = {"query": "Test query", "thread_id": "test_thread"}
    # 不带 Header 发送请求
    response = test_client.post("/chat", json=payload)
    assert response.status_code in [401, 403]


@pytest.mark.api
def test_chat_flow(test_client, auth_headers):
    """测试聊天主流程"""
    payload = {
        "query": "Hello AI",
        "thread_id": "test_123",
        "model_name": "deepseek/deepseek-chat",
    }

    # Patch 掉 agent graph 的执行，只测试接口连通性
    with patch(
        "agent.agent_graph.graph.astream_events",
        side_effect=mock_astream_events_generator,
    ):
        response = test_client.post("/chat", json=payload, headers=auth_headers)
        assert response.status_code == 200
        assert "Hello" in response.text


@pytest.mark.api
def test_tts_endpoint(test_client, auth_headers):
    """测试 TTS 接口"""
    # Mock 掉 AudioService
    with patch("services.audio_service.AudioService.generate_audio_file") as mock_gen:
        mock_gen.return_value = "/audio/test.mp3"

        response = test_client.post(
            "/tts", params={"text": "Hola"}, headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["url"] == "/audio/test.mp3"
