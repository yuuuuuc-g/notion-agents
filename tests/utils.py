"""
tests/utils.py
测试专用的辅助工具函数
"""
from unittest.mock import patch


# 模拟 LangChain 的 Chunk 对象
class MockChunk:
    def __init__(self, content):
        self.content = content


async def mock_astream_events_generator(*args, **kwargs):
    """
    模拟 LangGraph 的 astream_events 生成器
    接收任意参数以适配 ChatService 的调用
    """
    # 提取 responses，默认为 list
    responses = ["Hello", " from ", "AI"]

    # 模拟文本流
    for text in responses:
        yield {
            "event": "on_chat_model_stream",
            "data": {"chunk": MockChunk(content=text)},
        }


def mock_rate_limiting(test_func):
    """
    装饰器：跳过 time.sleep 以加速测试
    """

    async def wrapper(*args, **kwargs):
        with patch("asyncio.sleep", return_value=None):
            with patch("time.sleep", return_value=None):
                return await test_func(*args, **kwargs)

    return wrapper
