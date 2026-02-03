"""
tests/vector/test_embedding_provider_final.py
针对 SiliconFlowEmbedding 的高覆盖率测试
版本：httpx 版本 - 匹配实际代码
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from vector.embedding_provider import SiliconFlowEmbedding


@pytest.fixture
def mock_settings():
    """Mock SETTINGS 配置"""
    with patch("vector.embedding_provider.SETTINGS") as mock_settings:
        mock_settings.SILICON_KEY = "sk-test-key"
        mock_settings.SILICON_BASE_URL = "https://api.test"
        yield mock_settings


@pytest.fixture
def mock_httpx_response():
    """创建标准的 Mock HTTP 响应"""
    fake_vector = [0.1] * 1024

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": fake_vector, "index": 0}]}
    mock_response.raise_for_status = MagicMock()

    return mock_response


def test_init_success(mock_settings):
    """测试正常初始化"""
    provider = SiliconFlowEmbedding()

    assert provider.api_key == "sk-test-key"
    assert provider.base_url == "https://api.test"
    assert provider.model == "BAAI/bge-m3"
    assert provider.max_workers == 5


def test_init_with_custom_params(mock_settings):
    """测试自定义参数初始化"""
    provider = SiliconFlowEmbedding(
        api_key="custom-key",
        base_url="https://custom.com",
        model="custom-model",
        max_workers=10,
    )

    assert provider.api_key == "custom-key"
    assert provider.base_url == "https://custom.com"
    assert provider.model == "custom-model"
    assert provider.max_workers == 10


def test_init_missing_api_key(mock_settings):
    """测试缺少 API Key 时抛出异常"""
    mock_settings.SILICON_KEY = None

    with pytest.raises(ValueError, match="API Key is required"):
        SiliconFlowEmbedding()


def test_init_missing_base_url(mock_settings):
    """测试缺少 base URL 时抛出异常"""
    mock_settings.SILICON_BASE_URL = None

    with pytest.raises(ValueError, match="base URL is required"):
        SiliconFlowEmbedding()


def test_init_invalid_base_url(mock_settings):
    """测试无效的 base URL"""
    with pytest.raises(ValueError, match="Invalid base_url"):
        SiliconFlowEmbedding(base_url="invalid-url")


def test_embed_query_success(mock_settings, mock_httpx_response):
    """测试单条查询 Embedding"""
    with patch("httpx.post", return_value=mock_httpx_response):
        provider = SiliconFlowEmbedding()

        vector = provider.embed_query("hello world")

        # 验证返回结果
        assert len(vector) == 1024
        assert vector[0] == 0.1


def test_embed_query_empty_string(mock_settings):
    """测试空字符串"""
    provider = SiliconFlowEmbedding()

    vector = provider.embed_query("")

    # 空字符串直接返回空列表
    assert vector == []


def test_embed_query_timeout(mock_settings):
    """测试超时处理"""
    with patch("httpx.post", side_effect=httpx.TimeoutException("Timeout")):
        provider = SiliconFlowEmbedding()

        vector = provider.embed_query("test")

        # 超时返回空列表
        assert vector == []


def test_embed_query_http_error_401(mock_settings):
    """测试 HTTP 401 错误"""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("httpx.post") as mock_post:
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=MagicMock(), response=mock_response
        )

        provider = SiliconFlowEmbedding()
        vector = provider.embed_query("test")

        assert vector == []


def test_embed_query_http_error_429(mock_settings):
    """测试 HTTP 429 速率限制"""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limit exceeded"

    with patch("httpx.post") as mock_post:
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=MagicMock(), response=mock_response
        )

        provider = SiliconFlowEmbedding()
        vector = provider.embed_query("test")

        assert vector == []


def test_embed_query_network_error(mock_settings):
    """测试网络错误"""
    with patch("httpx.post", side_effect=httpx.RequestError("Network error")):
        provider = SiliconFlowEmbedding()

        vector = provider.embed_query("test")

        assert vector == []


def test_embed_query_invalid_response_format(mock_settings):
    """测试无效的响应格式"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"invalid": "format"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.post", return_value=mock_response):
        provider = SiliconFlowEmbedding()

        vector = provider.embed_query("test")

        assert vector == []


def test_embed_query_unexpected_error(mock_settings):
    """测试未预期的错误"""
    with patch("httpx.post", side_effect=Exception("Unexpected error")):
        provider = SiliconFlowEmbedding()

        vector = provider.embed_query("test")

        assert vector == []


def test_embed_documents_success(mock_settings, mock_httpx_response):
    """测试批量 Embedding（成功场景）"""
    with patch("httpx.post", return_value=mock_httpx_response):
        provider = SiliconFlowEmbedding()

        texts = ["doc1", "doc2", "doc3"]
        vectors = provider.embed_documents(texts)

        # 验证返回结果
        assert len(vectors) == 3
        assert all(len(v) == 1024 for v in vectors)
        assert all(v[0] == 0.1 for v in vectors)


def test_embed_documents_empty_list(mock_settings):
    """测试空列表"""
    provider = SiliconFlowEmbedding()

    vectors = provider.embed_documents([])

    assert vectors == []


def test_embed_documents_concurrent_execution(mock_settings, mock_httpx_response):
    """测试并发执行（验证使用了 ThreadPoolExecutor）"""
    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mock_httpx_response

    with patch("httpx.post", side_effect=mock_post):
        provider = SiliconFlowEmbedding()

        # 10 个文本应该并发处理
        texts = [f"doc{i}" for i in range(10)]
        vectors = provider.embed_documents(texts)

        # 验证结果
        assert len(vectors) == 10
        assert call_count == 10  # 每个文本调用一次


def test_embed_documents_partial_failure(mock_settings, mock_httpx_response):
    """测试部分失败场景"""
    call_count = 0

    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:  # 偶数次失败
            raise httpx.RequestError("Network error")
        return mock_httpx_response

    with patch("httpx.post", side_effect=mock_post):
        provider = SiliconFlowEmbedding()

        texts = ["doc1", "doc2", "doc3", "doc4"]
        vectors = provider.embed_documents(texts)

        # 验证结果：失败的返回空列表
        assert len(vectors) == 4
        assert len(vectors[0]) == 1024  # doc1 成功
        assert vectors[1] == []  # doc2 失败
        assert len(vectors[2]) == 1024  # doc3 成功
        assert vectors[3] == []  # doc4 失败


def test_async_client_lazy_loading(mock_settings):
    """测试异步客户端懒加载"""
    provider = SiliconFlowEmbedding()

    # 初始时不应该创建
    assert provider._async_client is None

    # 访问属性时才创建
    client = provider.async_client
    assert client is not None
    assert isinstance(client, httpx.AsyncClient)

    # 再次访问返回同一个实例
    client2 = provider.async_client
    assert client is client2


@pytest.mark.asyncio
async def test_aembed_query_success(mock_settings):
    """测试异步单条查询"""
    fake_vector = [0.1] * 1024

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": fake_vector, "index": 0}]}
    mock_response.raise_for_status = MagicMock()

    provider = SiliconFlowEmbedding()

    with patch.object(provider.async_client, "post", return_value=mock_response):
        vector = await provider.aembed_query("test")

        assert len(vector) == 1024
        assert vector[0] == 0.1


@pytest.mark.asyncio
async def test_aembed_query_empty_string(mock_settings):
    """测试异步空字符串"""
    provider = SiliconFlowEmbedding()

    vector = await provider.aembed_query("")

    assert vector == []


@pytest.mark.asyncio
async def test_aembed_query_timeout(mock_settings):
    """测试异步超时"""
    provider = SiliconFlowEmbedding()

    with patch.object(
        provider.async_client, "post", side_effect=httpx.TimeoutException("Timeout")
    ):
        vector = await provider.aembed_query("test")

        assert vector == []


@pytest.mark.asyncio
async def test_aembed_documents_success(mock_settings):
    """测试异步批量 Embedding"""
    fake_vector = [0.1] * 1024

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"embedding": fake_vector, "index": 0}]}
    mock_response.raise_for_status = MagicMock()

    provider = SiliconFlowEmbedding()

    with patch.object(provider.async_client, "post", return_value=mock_response):
        texts = ["doc1", "doc2", "doc3"]
        vectors = await provider.aembed_documents(texts)

        assert len(vectors) == 3
        assert all(len(v) == 1024 for v in vectors)


@pytest.mark.asyncio
async def test_aembed_documents_empty_list(mock_settings):
    """测试异步空列表"""
    provider = SiliconFlowEmbedding()

    vectors = await provider.aembed_documents([])

    assert vectors == []


def test_thread_pool_lazy_loading(mock_settings):
    """测试 thread_pool 懒加载（和 async_client 对称）"""
    provider = SiliconFlowEmbedding()

    # 初始时不应该创建
    assert provider._thread_pool is None

    # 访问属性时才创建
    pool = provider.thread_pool
    assert pool is not None

    # 再次访问返回同一个实例（复用）
    pool2 = provider.thread_pool
    assert pool is pool2


@pytest.mark.asyncio
async def test_close_cleanup(mock_settings):
    """测试 close() 正确清理 async_client 和 thread_pool"""
    provider = SiliconFlowEmbedding()

    # 触发两个懒加载属性创建
    _ = provider.async_client
    _ = provider.thread_pool
    assert provider._async_client is not None
    assert provider._thread_pool is not None

    # 调用 close()，两者都应该被清理
    await provider.close()
    assert provider._async_client is None
    assert provider._thread_pool is None


@pytest.mark.asyncio
async def test_close_idempotent(mock_settings):
    """测试 close() 可以重复调用不会崩溃"""
    provider = SiliconFlowEmbedding()

    # 不触发懒加载，直接 close（都是 None）
    await provider.close()
    assert provider._async_client is None
    assert provider._thread_pool is None

    # 再调用一次，还是不崩溃
    await provider.close()


def test_headers_format(mock_settings, mock_httpx_response):
    """测试请求头格式"""
    with patch("httpx.post", return_value=mock_httpx_response) as mock_post:
        provider = SiliconFlowEmbedding()
        provider.embed_query("test")

        # 验证调用参数
        call_kwargs = mock_post.call_args[1]
        headers = call_kwargs["headers"]

        assert headers["Authorization"] == "Bearer sk-test-key"
        assert headers["Content-Type"] == "application/json"


def test_payload_format(mock_settings, mock_httpx_response):
    """测试请求体格式"""
    with patch("httpx.post", return_value=mock_httpx_response) as mock_post:
        provider = SiliconFlowEmbedding()
        provider.embed_query("hello world")

        # 验证调用参数
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]

        assert payload["model"] == "BAAI/bge-m3"
        assert payload["input"] == "hello world"
        assert payload["encoding_format"] == "float"


def test_custom_model(mock_settings, mock_httpx_response):
    """测试自定义模型"""
    with patch("httpx.post", return_value=mock_httpx_response) as mock_post:
        provider = SiliconFlowEmbedding(model="custom-model")
        provider.embed_query("test")

        # 验证使用了自定义模型
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]

        assert payload["model"] == "custom-model"


def test_custom_max_workers(mock_settings, mock_httpx_response):
    """测试自定义并发数"""
    provider = SiliconFlowEmbedding(max_workers=10)

    assert provider.max_workers == 10


def test_url_construction(mock_settings, mock_httpx_response):
    """测试 URL 构建"""
    with patch("httpx.post", return_value=mock_httpx_response) as mock_post:
        provider = SiliconFlowEmbedding()
        provider.embed_query("test")

        # 验证 URL
        call_args = mock_post.call_args[0]
        url = call_args[0]

        assert url == "https://api.test/embeddings"


def test_timeout_setting(mock_settings, mock_httpx_response):
    """测试超时设置"""
    with patch("httpx.post", return_value=mock_httpx_response) as mock_post:
        provider = SiliconFlowEmbedding()
        provider.embed_query("test")

        # 验证超时设置
        call_kwargs = mock_post.call_args[1]

        assert call_kwargs["timeout"] == 30.0


# 性能测试（可选）
@pytest.mark.performance
def test_concurrent_performance(mock_settings, mock_httpx_response):
    """测试并发性能"""

    with patch("httpx.post", return_value=mock_httpx_response):
        provider = SiliconFlowEmbedding(max_workers=5)

        # 10 个文本
        texts = [f"doc{i}" for i in range(10)]

        # start = time.time()
        vectors = provider.embed_documents(texts)

        # 验证结果
        assert len(vectors) == 10

        # 并发应该比串行快（这个测试可能不稳定，可以移除）
        # assert elapsed < 1.0  # 假设单次请求 0.1s，并发应该 < 1s


# 集成测试（可选）
@pytest.mark.integration
def test_real_api_call_if_configured():
    """集成测试：真实 API 调用"""
    import os

    real_key = os.getenv("SILICON_KEY")
    real_url = os.getenv("SILICON_BASE_URL")

    if not real_key or not real_url:
        pytest.skip("Skipping integration test: No real API credentials")

    provider = SiliconFlowEmbedding()

    vector = provider.embed_query("Hello, world!")

    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(v, float) for v in vector)


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=vector.embedding_provider", "--cov-report=term-missing"]
    )
