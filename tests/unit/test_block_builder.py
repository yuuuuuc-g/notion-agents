"""
tests/unit/test_block_builder.py
测试 Markdown 到 Notion Block 的转换逻辑
"""
from notion.block_builder import markdown_to_blocks


def test_convert_headers():
    """测试标题转换"""
    md = "# Header 1\n## Header 2\n### Header 3"
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 3
    assert blocks[0]["type"] == "heading_1"
    assert blocks[0]["heading_1"]["rich_text"][0]["text"]["content"] == "Header 1"
    assert blocks[1]["type"] == "heading_2"
    assert blocks[2]["type"] == "heading_3"


def test_convert_paragraph():
    """测试普通段落"""
    md = "This is a simple paragraph."
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"
    assert (
        blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
        == "This is a simple paragraph."
    )


def test_convert_lists():
    """测试列表"""
    md = "- Item 1\n- Item 2"
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 2
    assert blocks[0]["type"] == "bulleted_list_item"
    assert (
        blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Item 1"
    )


def test_convert_code_block():
    """测试代码块"""
    md = "```python\nprint('Hello')\n```"
    blocks = markdown_to_blocks(md)

    # 注意：具体实现可能将代码块解析为1个或多个block，根据你的实现调整断言
    assert len(blocks) >= 1
    # 检查是否识别为代码类型
    has_code = any(b.get("type") == "code" for b in blocks)
    assert has_code


def test_convert_mixed_content():
    """测试混合内容"""
    md = """
# Title
Introduction text.

- Point A
- Point B

> Quote block
    """
    blocks = markdown_to_blocks(md)
    assert len(blocks) >= 4
    types = [b["type"] for b in blocks]
    assert "heading_1" in types
    assert "paragraph" in types
    assert "bulleted_list_item" in types
    # 引用块在某些解析器中可能被视为段落或callout，视具体实现而定
