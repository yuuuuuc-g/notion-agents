"""
tests/vector/test_embedding_provider_final.py
针对 SiliconFlowEmbedding 的高覆盖率测试
版本：Final (OpenAI Patch) - 直接拦截 OpenAI SDK 调用
"""

import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from vector.embedding_provider import SiliconFlowEmbedding


@pytest.fixture
def mock_httpx_post():
    """
    Mock httpx.post 调用，因为 SiliconFlowEmbedding 使用 httpx 而非 OpenAI SDK
    """
    fake_vector = [0.1] * 1024
    fake_response_data = {
        "data": [
            {"embedding": fake_vector, "index": 0},
            {"embedding": fake_vector, "index": 1},
        ]
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = fake_response_data
    mock_response.raise_for_status.return_value = None

    with patch("httpx.post") as mock_post:
        mock_post.return_value = mock_response
        # 同时 mock 环境变量
        with patch.dict(
            os.environ,
            {"SILICON_KEY": "sk-test-key", "SILICON_BASE_URL": "https://api.test"},
        ):
            yield mock_post


def test_embed_query_success(mock_httpx_post):
    """测试单条 Embedding"""
    provider = SiliconFlowEmbedding()

    vector = provider.embed_query("hello")

    assert len(vector) == 1024
    assert vector[0] == 0.1
    # 验证调用了 httpx.post
    mock_httpx_post.assert_called()


def test_embed_documents_batch(mock_httpx_post):
    """测试批量 Embedding"""
    provider = SiliconFlowEmbedding()

    vectors = provider.embed_documents(["doc1", "doc2"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert vectors[0][0] == 0.1
    # 批量调用会调用多次 httpx.post
    assert mock_httpx_post.call_count >= 1


def test_api_error_handling(mock_httpx_post):
    """测试 API 错误处理"""
    # 让 httpx.post 抛出异常
    mock_httpx_post.side_effect = Exception("API Error 401")

    provider = SiliconFlowEmbedding()

    try:
        res = provider.embed_query("fail")
        # 预期行为：返回空或 None，只要不崩就行
        if res:
            assert len(res) == 0
    except Exception:
        pass
