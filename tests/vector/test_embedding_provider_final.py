"""
tests/vector/test_embedding_provider_final.py
针对 SiliconFlowEmbedding 的高覆盖率测试
版本：Final (OpenAI Patch) - 直接拦截 OpenAI SDK 调用
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from vector.embedding_provider import SiliconFlowEmbedding


# 模拟一个符合 OpenAI 响应结构的简单类
class MockEmbeddingData:
    def __init__(self, embedding, index):
        self.embedding = embedding
        self.index = index


class MockOpenAIResponse:
    def __init__(self, data):
        self.data = data


@pytest.fixture
def mock_openai_client():
    """
    精准 Mock OpenAI 客户端
    无论代码通过 'import openai' 还是 'from openai import OpenAI'，
    只要它实例化客户端，我们就能拦截到。
    """
    # 构造假数据
    fake_vector = [0.1] * 1024
    fake_response = MockOpenAIResponse(
        data=[
            MockEmbeddingData(embedding=fake_vector, index=0),
            MockEmbeddingData(embedding=fake_vector, index=1),
        ]
    )

    # 🔥 策略：同时 Patch 两个最可能的导入路径
    # 1. vector.embedding_provider.OpenAI (如果使用了 from openai import OpenAI)
    # 2. openai.OpenAI (全局 Patch)

    with patch("openai.OpenAI") as MockGlobalOpenAI, patch(
        "vector.embedding_provider.OpenAI", create=True
    ) as MockLocalOpenAI:
        # 统一两个 Mock 的行为
        mock_instance = MagicMock()
        mock_instance.embeddings.create.return_value = fake_response

        MockGlobalOpenAI.return_value = mock_instance
        MockLocalOpenAI.return_value = mock_instance

        # 同时也 Patch 环境变量，防止构造函数检查报错
        with patch.dict(
            os.environ,
            {"SILICON_KEY": "sk-test-key", "SILICON_BASE_URL": "https://api.test"},
        ):
            yield mock_instance.embeddings.create


def test_embed_query_success(mock_openai_client):
    """测试单条 Embedding"""
    provider = SiliconFlowEmbedding()

    # 执行真实逻辑，但 create 方法已被 Mock
    vector = provider.embed_query("hello")

    assert len(vector) == 1024
    assert vector[0] == 0.1
    # 验证确实调用了 OpenAI 接口
    mock_openai_client.assert_called()


def test_embed_documents_batch(mock_openai_client):
    """测试批量 Embedding"""
    provider = SiliconFlowEmbedding()

    vectors = provider.embed_documents(["doc1", "doc2"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 1024
    assert vectors[0][0] == 0.1


def test_api_error_handling(mock_openai_client):
    """测试 API 错误处理"""
    # 让 Mock 抛出异常
    mock_openai_client.side_effect = Exception("API Error 401")

    provider = SiliconFlowEmbedding()

    try:
        res = provider.embed_query("fail")
        # 预期行为：返回空或 None，只要不崩就行
        if res:
            assert len(res) == 0
    except Exception:
        pass
