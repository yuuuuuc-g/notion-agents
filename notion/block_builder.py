"""
notion/block_builder.py
Markdown -> Notion Blocks 转换器 (Hardened Edition)
已修复:
1. 列表项解析偶尔丢失 data object 的问题
2. 引用块 (Quote) 恢复支持嵌套
3. 增强的表格和代码块检测
"""

import re
from typing import List, Dict, Any, Optional


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def parse_rich_text(text: str) -> List[Dict]:
    """解析 Markdown 行内样式"""
    if not text:
        return [{"type": "text", "text": {"content": " "}}]  # 防止空内容报错

    rich_text = []

    # 简单的正则分割，支持代码、公式、链接、加粗、斜体、删除线
    pattern = re.compile(
        r"(`[^`]+`|\$[^\$]+\$|\[[^\]]+\]\([^\)]+\)|\*\*.+?\*\*|\*[^\*]+\*|~[^~]+~)"
    )

    parts = pattern.split(text)

    for part in parts:
        if not part:
            continue

        # 统一构建函数
        def add_text(content, annotations=None, url=None):
            if not content:
                return

            # 🔥 Notion 2000 字符硬限制保护
            if len(content) > 2000:
                content = content[:1997] + "..."

            obj = {"type": "text", "text": {"content": content}}
            if url:
                obj["text"]["link"] = {"url": url}
            if annotations:
                obj["annotations"] = annotations
            rich_text.append(obj)

        # 匹配逻辑
        if part.startswith("$") and part.endswith("$") and len(part) > 2:
            rich_text.append(
                {"type": "equation", "equation": {"expression": part[1:-1]}}
            )
        elif part.startswith("`") and part.endswith("`"):
            add_text(part[1:-1], {"code": True})
        elif part.startswith("[") and part.endswith(")") and "](" in part:
            try:
                split_idx = part.rindex("](")
                link_text = part[1:split_idx]
                link_url = part[split_idx + 2 : -1].strip()
                if link_url:
                    add_text(link_text, url=link_url)
                else:
                    add_text(part)
            except (ValueError, IndexError):
                add_text(part)
        elif part.startswith("**") and part.endswith("**") and len(part) > 4:
            add_text(part[2:-2], {"bold": True})
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            add_text(part[1:-1], {"italic": True})
        elif part.startswith("~") and part.endswith("~") and len(part) > 2:
            add_text(part[1:-1], {"strikethrough": True})
        else:
            add_text(part)

    if not rich_text:
        return [{"type": "text", "text": {"content": " "}}]

    return rich_text


def _flush_table(table_rows: List[List[str]]) -> Optional[Dict]:
    if not table_rows:
        return None
    width = max(len(row) for row in table_rows) if table_rows else 0
    if width == 0:
        return None
    table_children = []
    for row_cells in table_rows:
        current_cells = row_cells + [""] * (width - len(row_cells))
        notion_cells = [parse_rich_text(cell) for cell in current_cells]
        table_children.append(
            {"type": "table_row", "table_row": {"cells": notion_cells}}
        )
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "children": table_children,
        },
    }


def markdown_to_blocks(markdown_text: str) -> List[Dict]:
    if not markdown_text:
        return []
    lines = markdown_text.split("\n")

    code_mode = False
    code_content = []
    code_lang = "plain text"
    math_mode = False
    math_content = []
    table_rows = []

    root_blocks = []
    # 栈结构：用于处理嵌套 (Indentation)
    stack = [{"children": root_blocks, "indent": -1, "type": "root"}]

    for line in lines:
        original_line = line
        stripped = line.strip()

        # 1. 处理空行 (代码块/公式块内保留，否则跳过)
        if not stripped:
            if code_mode:
                code_content.append("")
            if math_mode:
                math_content.append("")
            continue

        # 计算缩进层级 (2空格 = 1层)
        indent_spaces = len(original_line) - len(original_line.lstrip(" "))
        current_indent = indent_spaces // 2

        # --- Special Blocks (Code, Math, Table) ---
        # 这一部分逻辑保持优先，不受缩进影响
        if stripped.startswith("$$"):
            if stripped.endswith("$$") and len(stripped) > 2:
                # 行内公式块
                stack[-1]["children"].append(
                    {
                        "object": "block",
                        "type": "equation",
                        "equation": {"expression": stripped[2:-2].strip()},
                    }
                )
                continue
            if math_mode:
                # 结束公式块
                stack[-1]["children"].append(
                    {
                        "object": "block",
                        "type": "equation",
                        "equation": {"expression": "\n".join(math_content)},
                    }
                )
                math_mode = False
                math_content = []
            else:
                # 开始公式块
                if table_rows:
                    t = _flush_table(table_rows)
                    stack[-1]["children"].append(t) if t else None
                    table_rows = []
                math_mode = True
            continue
        if math_mode:
            math_content.append(line)
            continue

        if stripped.startswith("```"):
            if code_mode:
                # 结束代码块
                full_code = "\n".join(code_content)
                if len(full_code) > 2000:
                    full_code = full_code[:1999]
                stack[-1]["children"].append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [
                                {"type": "text", "text": {"content": full_code}}
                            ],
                            "language": code_lang,
                        },
                    }
                )
                code_mode = False
                code_content = []
            else:
                # 开始代码块
                if table_rows:
                    t = _flush_table(table_rows)
                    stack[-1]["children"].append(t) if t else None
                    table_rows = []
                code_mode = True
                lang = stripped[3:].strip()
                code_lang = lang[:20].lower() if lang else "plain text"
            continue
        if code_mode:
            code_content.append(line)
            continue

        # 表格行检测
        if stripped.startswith("|"):
            clean_cells = [c.strip() for c in stripped.strip("|").split("|")]
            # 简单的分隔线检测 (e.g. ---|---)
            if not all(re.match(r"^[-: ]+$", c) for c in clean_cells if c):
                table_rows.append(clean_cells)
            continue
        if table_rows:
            t = _flush_table(table_rows)
            stack[-1]["children"].append(t) if t else None
            table_rows = []

        # --- Nested Block Logic ---
        # 如果当前缩进 <= 栈顶缩进，说明退出了嵌套，弹栈
        while len(stack) > 1 and current_indent <= stack[-1]["indent"]:
            stack.pop()

        parent_list = stack[-1]["children"]
        is_container = False
        new_block = None

        # 使用正则进行更精准的匹配

        # Headings
        if stripped.startswith("# "):
            new_block = {
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": parse_rich_text(stripped[2:])},
            }
        elif stripped.startswith("## "):
            new_block = {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": parse_rich_text(stripped[3:])},
            }
        elif stripped.startswith("### ") or stripped.startswith("#### "):
            content = stripped[4:] if stripped.startswith("### ") else stripped[5:]
            new_block = {
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": parse_rich_text(content)},
            }

        # Lists (Bulleted)
        # 修复：兼容 "- Item" 和 "- **Bold**"
        elif re.match(r"^[-*]\s+", stripped):
            # 提取内容 (去掉 "- " 或 "* ")
            content = re.sub(r"^[-*]\s+", "", stripped, count=1)
            new_block = {
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": parse_rich_text(content)},
            }
            # 列表项是容器，可以嵌套
            # 熔断机制：防止过深 (Notion 限制 3 层，这里我们宽容一点，API 会自己报错如果太深，但通常3层够了)
            is_container = True if len(stack) < 5 else False

        # Lists (Numbered)
        elif re.match(r"^\d+\.\s+", stripped):
            content = re.sub(r"^\d+\.\s+", "", stripped, count=1)
            new_block = {
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": parse_rich_text(content)},
            }
            is_container = True if len(stack) < 5 else False

        # Quote (引用)
        elif stripped.startswith("> "):
            content = stripped[2:].strip()
            new_block = {
                "object": "block",
                "type": "quote",
                "quote": {"rich_text": parse_rich_text(content)},
            }
            # 恢复 Quote 为容器，支持嵌套
            is_container = True if len(stack) < 5 else False

        # Paragraph (默认)
        else:
            new_block = {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": parse_rich_text(stripped)},
            }
            is_container = (
                False  # 段落一般不作为容器处理嵌套，除非为了 Callout (这里暂不支持)
            )

        # Append & Push Stack
        if new_block:
            parent_list.append(new_block)

            if is_container:
                new_block["children"] = []
                stack.append(
                    {"children": new_block["children"], "indent": current_indent}
                )

    # 处理循环结束后残留的表格
    if table_rows:
        t = _flush_table(table_rows)
        stack[-1]["children"].append(t) if t else None

    def _clean_empty_children(blocks_list):
        """递归清理空的 children 字段，防止 Notion 报错"""
        for block in blocks_list:
            if "children" in block:
                if not block["children"]:
                    del block["children"]
                else:
                    _clean_empty_children(block["children"])

    _clean_empty_children(root_blocks)
    return root_blocks
