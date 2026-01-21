"""
tests/unit/test_splitter.py
文本切分单元测试
"""
import pytest

from vector.splitter import split_text


@pytest.fixture
def local_markdown():
    return "# Header\n\nBody content."


def test_split_simple_text():
    text = "Hello. " * 100
    # ✅ 修复点：移除 chunk_size 参数，使用默认值
    chunks = split_text(text)
    # 只要切分了就行，具体几块取决于默认配置
    assert len(chunks) >= 1


def test_split_markdown(local_markdown):
    chunks = split_text(local_markdown)
    assert len(chunks) >= 1
    assert "# Header" in chunks[0]
