"""
tests/unit/test_block_builder_comprehensive.py
Block Builder 完整测试套件 - 提升覆盖率到 90%+

目标覆盖的未测试区域：
- rich_text 解析（公式、链接、加粗、斜体、代码）
- 表格处理
- 代码块语言检测
- 数学块
- 编号列表
- 分隔线
- 嵌套结构
"""
import pytest

from notion.block_builder import (
    _flush_table,
    _safe_str,
    markdown_to_blocks,
    parse_rich_text,
)


# ===================================================================
# 测试 _safe_str 辅助函数
# ===================================================================
def test_safe_str_with_none():
    """测试 None 值转换"""
    assert _safe_str(None) == ""


def test_safe_str_with_string():
    """测试字符串转换"""
    assert _safe_str("hello") == "hello"
    assert _safe_str("  hello  ") == "hello"  # 应该 strip


def test_safe_str_with_number():
    """测试数字转换"""
    assert _safe_str(123) == "123"
    assert _safe_str(3.14) == "3.14"


# ===================================================================
# 测试 parse_rich_text（行内样式）
# ===================================================================
def test_parse_rich_text_empty():
    """测试空文本"""
    result = parse_rich_text("")
    assert len(result) == 1
    assert result[0]["text"]["content"] == " "  # 返回空格占位


def test_parse_rich_text_plain():
    """测试纯文本"""
    result = parse_rich_text("Hello World")
    assert len(result) == 1
    assert result[0]["type"] == "text"
    assert result[0]["text"]["content"] == "Hello World"


def test_parse_rich_text_bold():
    """测试加粗"""
    result = parse_rich_text("**bold text**")
    assert len(result) == 1
    assert result[0]["text"]["content"] == "bold text"
    assert result[0]["annotations"]["bold"] is True


def test_parse_rich_text_italic():
    """测试斜体"""
    result = parse_rich_text("*italic text*")
    assert len(result) == 1
    assert result[0]["text"]["content"] == "italic text"
    assert result[0]["annotations"]["italic"] is True


def test_parse_rich_text_code():
    """测试行内代码"""
    result = parse_rich_text("`code here`")
    assert len(result) == 1
    assert result[0]["text"]["content"] == "code here"
    assert result[0]["annotations"]["code"] is True


def test_parse_rich_text_strikethrough():
    """测试删除线"""
    result = parse_rich_text("~deleted~")
    assert len(result) == 1
    assert result[0]["text"]["content"] == "deleted"
    assert result[0]["annotations"]["strikethrough"] is True


def test_parse_rich_text_equation():
    """测试行内公式"""
    result = parse_rich_text("$E=mc^2$")
    assert len(result) == 1
    assert result[0]["type"] == "equation"
    assert result[0]["equation"]["expression"] == "E=mc^2"


def test_parse_rich_text_link():
    """测试链接"""
    result = parse_rich_text("[Google](https://google.com)")
    assert len(result) == 1
    assert result[0]["text"]["content"] == "Google"
    assert result[0]["text"]["link"]["url"] == "https://google.com"


def test_parse_rich_text_mixed():
    """测试混合样式"""
    result = parse_rich_text("Plain **bold** `code` *italic*")
    # 应该解析为多个部分
    assert len(result) >= 4
    types = [r.get("annotations", {}).get("bold") for r in result]
    assert True in types  # 至少有一个加粗


def test_parse_rich_text_long_truncate():
    """测试超长文本截断（2000字符限制）"""
    long_text = "A" * 2500
    result = parse_rich_text(long_text)
    # 应该被截断到 1990 + "..."
    content = result[0]["text"]["content"]
    assert len(content) <= 2000
    assert content.endswith("...")


# ===================================================================
# 测试 _flush_table（表格处理）
# ===================================================================
def test_flush_table_empty():
    """测试空表格"""
    result = _flush_table([])
    assert result is None


def test_flush_table_simple():
    """测试简单表格"""
    rows = [
        ["Name", "Age"],
        ["Alice", "25"],
        ["Bob", "30"],
    ]
    result = _flush_table(rows)

    assert result["type"] == "table"
    assert result["table"]["table_width"] == 2
    assert result["table"]["has_column_header"] is True
    assert len(result["table"]["children"]) == 3  # 3行


def test_flush_table_uneven_rows():
    """测试不规则表格（列数不一致）"""
    rows = [
        ["A", "B", "C"],
        ["1", "2"],  # 缺少一列
        ["X"],  # 缺少两列
    ]
    result = _flush_table(rows)

    # 应该自动填充到最大宽度
    assert result["table"]["table_width"] == 3
    # 所有行都应该有3列（自动填充空字符串）


# ===================================================================
# 测试 markdown_to_blocks（完整转换）
# ===================================================================
def test_markdown_to_blocks_empty():
    """测试空输入"""
    blocks = markdown_to_blocks("")
    assert blocks == []


def test_markdown_to_blocks_heading_4():
    """测试四级标题（应降级为 heading_3）"""
    md = "#### Level 4 Heading"
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "heading_3"  # 自动降级


def test_markdown_to_blocks_numbered_list():
    """测试编号列表"""
    md = "1. First\n2. Second\n3. Third"
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 3
    assert all(b["type"] == "numbered_list_item" for b in blocks)
    assert blocks[0]["numbered_list_item"]["rich_text"][0]["text"]["content"] == "First"


def test_markdown_to_blocks_divider():
    """测试分隔线"""
    md = "Text above\n\n---\n\nText below"
    blocks = markdown_to_blocks(md)

    types = [b["type"] for b in blocks]
    assert "divider" in types


def test_markdown_to_blocks_code_with_language():
    """测试带语言标识的代码块"""
    md = "```python\nprint('hello')\n```"
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "python"


def test_markdown_to_blocks_code_unsupported_language():
    """测试不支持的语言（应回退到 plain text）"""
    md = "```foobar\ncode\n```"
    blocks = markdown_to_blocks(md)

    assert blocks[0]["code"]["language"] == "plain text"


def test_markdown_to_blocks_math_block():
    """测试数学块"""
    md = "$$\nE = mc^2\n$$"
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "equation"
    assert "E = mc^2" in blocks[0]["equation"]["expression"]


def test_markdown_to_blocks_table():
    """测试表格解析"""
    md = """
| Name  | Age |
|-------|-----|
| Alice | 25  |
| Bob   | 30  |
"""
    blocks = markdown_to_blocks(md)

    # 应该生成一个 table block
    table_blocks = [b for b in blocks if b.get("type") == "table"]
    assert len(table_blocks) == 1

    table = table_blocks[0]
    assert table["table"]["table_width"] == 2
    # 注意：分隔行不计入数据行
    assert len(table["table"]["children"]) == 3  # 表头 + 2行数据


def test_markdown_to_blocks_table_separator_only():
    """测试表格分隔行被正确跳过"""
    md = """
| A | B |
|---|---|
| 1 | 2 |
"""
    blocks = markdown_to_blocks(md)

    table = next(b for b in blocks if b["type"] == "table")
    # 分隔行应该被过滤掉
    children = table["table"]["children"]

    # 【修复】添加断言逻辑，使用这个变量
    # 原本有3行文本，去掉中间的分隔行后，应该只剩 2 行（表头 + 数据）
    assert len(children) == 2, f"应该只剩2行，实际有 {len(children)} 行"

    # 进一步验证：确保剩下的行里没有分隔符内容
    # children 的结构是 table_row -> cells -> rich_text
    first_row_cell = children[0]["table_row"]["cells"][0][0]["text"]["content"]
    assert "---" not in first_row_cell


def test_markdown_to_blocks_nested_lists():
    """测试嵌套列表（最大3层）"""
    md = """
- Level 1
  - Level 2
    - Level 3
      - Level 4 (应该被限制)
"""
    blocks = markdown_to_blocks(md)

    # 第一个 block 应该有 children
    assert "children" in blocks[0]
    # 嵌套深度应该被限制


def test_markdown_to_blocks_quote():
    """测试引用块"""
    md = "> This is a quote"
    blocks = markdown_to_blocks(md)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"
    assert blocks[0]["quote"]["rich_text"][0]["text"]["content"] == "This is a quote"


def test_markdown_to_blocks_mixed_complex():
    """测试复杂混合内容"""
    md = """
# Title

Introduction paragraph with **bold** and *italic*.

- List item 1
- List item 2


```python
def hello():
    print("world")
```


| Col1 | Col2 |
|------|------|
| A    | B    |

> Quote at the end

---

Final paragraph.
"""
    blocks = markdown_to_blocks(md)

    # 验证包含所有主要类型
    types = {b["type"] for b in blocks}
    assert "heading_1" in types
    assert "paragraph" in types
    assert "bulleted_list_item" in types
    assert "code" in types
    assert "table" in types
    assert "quote" in types
    assert "divider" in types


def test_markdown_to_blocks_cleanup_empty_children():
    """测试空 children 被清理"""
    md = "- Item without children"
    blocks = markdown_to_blocks(md)

    # children 如果为空应该被删除
    if "children" in blocks[0]:
        assert len(blocks[0]["children"]) > 0


def test_markdown_to_blocks_code_without_backticks():
    """测试代码块闭合（确保状态机正确）"""
    md = "```python\ncode\n```\nNormal text"
    blocks = markdown_to_blocks(md)

    # 应该有2个block：code + paragraph
    assert len(blocks) == 2
    assert blocks[0]["type"] == "code"
    assert blocks[1]["type"] == "paragraph"


def test_markdown_to_blocks_multiple_tables():
    """测试多个表格"""
    md = """
| T1 | A |
|----|---|
| 1  | 2 |

Some text

| T2 | B |
|----|---|
| 3  | 4 |
"""
    blocks = markdown_to_blocks(md)

    table_count = sum(1 for b in blocks if b["type"] == "table")
    assert table_count == 2


def test_markdown_to_blocks_table_at_end():
    """测试文件末尾的表格（边界情况）"""
    md = """
| A | B |
|---|---|
| 1 | 2 |"""  # 注意：没有结尾换行

    blocks = markdown_to_blocks(md)

    # 应该正确刷新表格（即使文件结尾）
    assert any(b["type"] == "table" for b in blocks)


# ===================================================================
# 边界情况测试
# ===================================================================
def test_markdown_to_blocks_only_whitespace():
    """测试纯空白"""
    md = "   \n\n   \n"
    blocks = markdown_to_blocks(md)

    # 空行应该被跳过
    assert blocks == []


def test_markdown_to_blocks_special_chars():
    """测试特殊字符"""
    md = "Text with <html> & \"quotes\" and 'apostrophes'"
    blocks = markdown_to_blocks(md)

    # 应该保持原样（不转义）
    content = blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]
    assert "<html>" in content


def test_parse_rich_text_malformed_link():
    """测试格式错误的链接"""
    result = parse_rich_text("[broken link](")
    # 应该不崩溃，作为普通文本处理
    assert len(result) >= 1


def test_markdown_to_blocks_unclosed_code_block():
    """测试未闭合的代码块（末尾）"""
    md = "```python\ncode without closing"
    blocks = markdown_to_blocks(md)

    # 【修复】添加断言，使用 blocks 变量
    # 验证解析器是否足够健壮，能够自动闭合文件末尾的代码块
    assert len(blocks) == 1
    assert blocks[0]["type"] == "code"

    # 验证内容是否被正确捕获
    content = blocks[0]["code"]["rich_text"][0]["text"]["content"]
    assert content == "code without closing"
    # 验证语言是否被正确捕获（即使没有闭合符）
    assert blocks[0]["code"]["language"] == "python"


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=notion.block_builder", "--cov-report=term-missing"]
    )
