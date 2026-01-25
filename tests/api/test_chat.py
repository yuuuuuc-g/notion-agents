"""
tests/api/test_chat.py
测试 Chat 接口
"""
from unittest.mock import MagicMock


async def mock_stream_gen(*args, **kwargs):
    yield "Hello"
    yield " World"


def test_chat_requires_auth(client):
    response = client.post("/api/chat", json={"query": "hi"})
    assert response.status_code in [401, 403]


def test_chat_flow(client, auth_headers, mock_container):
    mock_chat = mock_container.chat_service()

    # 🔥 关键修复：直接替换 stream_response 方法
    mock_chat.stream_response = MagicMock(side_effect=mock_stream_gen)

    response = client.post(
        "/api/chat", json={"query": "hello", "thread_id": "test"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert "Hello World" in response.text


def test_tts_endpoint(client, auth_headers, mock_container):
    # Audio Service 已经在 conftest 中配置了
    # SimpleAudioServiceMock 默认返回 "/mock/path/to/audio.mp3"

    response = client.post("/api/tts", params={"text": "Hola"}, headers=auth_headers)
    assert response.status_code == 200
    # 🔥 修复：匹配 SimpleAudioServiceMock 的实际返回值
    assert response.json()["url"] == "/mock/path/to/audio.mp3"
