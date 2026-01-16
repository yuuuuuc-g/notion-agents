"""
notion/block_builder.py
Master Final Edition: 补齐缺失引用，恢复全量 Block 支持
"""
import re
from typing import Any, Dict, List, Optional


def _safe_str(val: Any) -> str:
    """补回缺失的辅助函数，用于安全转换字符串"""
    if val is None:
        return ""
    return str(val).strip()


def parse_rich_text(text: str) -> List[Dict[str, Any]]:
    """解析 Markdown 行内样式，增加 2000 字符硬防御"""
    if not text:
        return [{"type": "text", "text": {"content": " "}}]

    # 物理限制保护
    if len(text) > 2000:
        text = text[:1990] + "..."

    rich_text: List[Dict[str, Any]] = []
    # 匹配公式、加粗、代码、链接、斜体、删除线
    pattern = re.compile(
        r"(`[^`]+`|\$[^\$]+\$|\[[^\]]+\]\([^\)]+\)|\*\*.+?\*\*|\*[^\*]+\*|~[^~]+~)"
    )
    parts = pattern.split(text)

    for part in parts:
        if not part:
            continue

        def add_text(
            content: str,
            annotations: Optional[Dict[str, Any]] = None,
            url: Optional[str] = None,
        ) -> None:
            if not content:
                return
            obj: Dict[str, Any] = {"type": "text", "text": {"content": content}}
            if url:
                obj["text"]["link"] = {"url": url}
            if annotations:
                obj["annotations"] = annotations
            rich_text.append(obj)

        if part.startswith("$") and part.endswith("$"):
            rich_text.append(
                {"type": "equation", "equation": {"expression": part[1:-1]}}
            )
        elif part.startswith("`"):
            add_text(part[1:-1], {"code": True})
        elif part.startswith("[") and "](" in part:
            try:
                idx = part.rindex("](")
                add_text(part[1:idx], url=part[idx + 2 : -1].strip())
            except Exception:
                add_text(part)
        elif part.startswith("**"):
            add_text(part[2:-2], {"bold": True})
        elif part.startswith("*"):
            add_text(part[1:-1], {"italic": True})
        elif part.startswith("~"):
            add_text(part[1:-1], {"strikethrough": True})
        else:
            add_text(part)
    return rich_text if rich_text else [{"type": "text", "text": {"content": " "}}]


def _flush_table(table_rows: List[List[str]]) -> Optional[Dict[str, Any]]:
    """处理表格解析"""
    if not table_rows:
        return None
    width = max(len(row) for row in table_rows)
    table_children: List[Dict[str, Any]] = []
    for row in table_rows:
        cells = (row + [""] * width)[:width]
        notion_cells = [parse_rich_text(cell) for cell in cells]
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


def markdown_to_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    if not markdown_text:
        return []
    lines = markdown_text.split("\n")
    root_blocks: List[Dict[str, Any]] = []
    # Explicit type for stack
    stack: List[Dict[str, Any]] = [{"children": root_blocks, "indent": -1}]

    # 状态机变量
    code_mode: bool = False
    math_mode: bool = False
    code_content: List[str] = []
    math_content: List[str] = []
    table_rows: List[List[str]] = []

    for line in lines:
        stripped = line.strip()

        # 1. 特殊块判定 (优先级最高)
        if stripped.startswith("```"):
            if code_mode:
                content: str = "\n".join(code_content)
                stack[-1]["children"].append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [
                                {"type": "text", "text": {"content": content[:2000]}}
                            ],
                            "language": "plain text",
                        },
                    }
                )
                code_mode = False
                code_content = []
            else:
                code_mode = True
                continue
        if code_mode:
            code_content.append(line)
            continue

        if stripped.startswith("$$"):
            if math_mode:
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
                math_mode = True
            continue
        if math_mode:
            math_content.append(line)
            continue

        if stripped.startswith("|"):
            cells: List[str] = [c.strip() for c in stripped.strip("|").split("|")]
            if not all(re.match(r"^[-: ]+$", c) for c in cells if c):
                table_rows.append(cells)
            continue
        elif table_rows:
            t = _flush_table(table_rows)
            if t:
                stack[-1]["children"].append(t)
            table_rows = []

        if not stripped:
            continue

        # 2. 嵌套缩进处理
        indent = (len(line) - len(line.lstrip())) // 2
        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()

        new_block: Optional[Dict[str, Any]] = None
        is_container: bool = False

        # 3. 标题识别与自动降级 (解决 #### 问题)
        if stripped.startswith("# "):
            new_block = {
                "type": "heading_1",
                "heading_1": {"rich_text": parse_rich_text(stripped[2:])},
            }
        elif stripped.startswith("## "):
            new_block = {
                "type": "heading_2",
                "heading_2": {"rich_text": parse_rich_text(stripped[3:])},
            }
        elif stripped.startswith("### ") or stripped.startswith("#### "):
            new_block = {
                "type": "heading_3",
                "heading_3": {
                    "rich_text": parse_rich_text(re.sub(r"^#+\s+", "", stripped))
                },
            }

        # 4. 列表与引用
        elif re.match(r"^[-*]\s+", stripped):
            new_block = {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": parse_rich_text(stripped[2:])},
            }
            is_container = True
        elif stripped.startswith("> "):
            new_block = {
                "type": "quote",
                "quote": {"rich_text": parse_rich_text(stripped[2:])},
            }
            is_container = True
        else:
            new_block = {
                "type": "paragraph",
                "paragraph": {"rich_text": parse_rich_text(stripped)},
            }

        if new_block:
            new_block["object"] = "block"
            stack[-1]["children"].append(new_block)
            # 限制嵌套深度为 3，确保 API 稳健
            if is_container and len(stack) < 3:
                new_block["children"] = []
                stack.append({"children": new_block["children"], "indent": indent})

    # 清理残留表格
    if table_rows:
        t = _flush_table(table_rows)
        if t:
            stack[-1]["children"].append(t)

    def _clean(blocks: List[Dict[str, Any]]) -> None:
        for b in blocks:
            if "children" in b:
                if not b["children"]:
                    del b["children"]
                else:
                    _clean(b["children"])

    _clean(root_blocks)
    return root_blocks
