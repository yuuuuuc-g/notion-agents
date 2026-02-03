"""
notion/block_builder.py
Master Final Edition v2: 修复嵌套和表格写入问题
修复内容：
  1. numbered_list_item 添加为 container（支持嵌套）
  2. _flush_table 的 table_row 添加 "object": "block"
  3. 嵌套深度限制对齐 Notion API（最大 3 层子块）
  4. 表格解析更加严格（处理边界情况）
"""
import re
from typing import Any, Dict, List, Optional


def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def parse_rich_text(text: str) -> List[Dict[str, Any]]:
    """解析 Markdown 行内样式，增加 2000 字符硬防御"""
    if not text:
        return [{"type": "text", "text": {"content": " "}}]

    if len(text) > 2000:
        text = text[:1990] + "..."

    rich_text: List[Dict[str, Any]] = []
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
    """
    处理表格解析
    🔥 修复：table_row 添加 "object": "block"
    """
    if not table_rows:
        return None

    width = max(len(row) for row in table_rows)
    table_children: List[Dict[str, Any]] = []

    for row in table_rows:
        cells = (row + [""] * width)[:width]
        notion_cells = [parse_rich_text(cell) for cell in cells]
        table_children.append(
            {
                "object": "block",  # 🔥 新增
                "type": "table_row",
                "table_row": {"cells": notion_cells},
            }
        )

    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "children": table_children,  # table_row 随 table 一起写入
        },
    }


def _is_separator_row(cells: List[str]) -> bool:
    """
    判断是否是表格分隔行
    例如：|---|---|---| 或 |:---|:---:|---:|
    """
    if not cells:
        return False
    return all(re.match(r"^[-:| ]+$", c) for c in cells if c.strip())


def markdown_to_blocks(markdown_text: str) -> List[Dict[str, Any]]:
    if not markdown_text:
        return []

    lines = markdown_text.split("\n")
    root_blocks: List[Dict[str, Any]] = []
    stack: List[Dict[str, Any]] = [{"children": root_blocks, "indent": -1}]

    # 状态机变量
    code_mode: bool = False
    math_mode: bool = False
    code_content: List[str] = []
    code_language: str = "plain text"
    math_content: List[str] = []
    table_rows: List[List[str]] = []

    for line in lines:
        stripped = line.strip()

        # =====================
        # 1. 代码块
        # =====================
        if stripped.startswith("```"):
            if code_mode:
                # 代码块结束
                content: str = "\n".join(code_content)
                stack[-1]["children"].append(
                    {
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [
                                {"type": "text", "text": {"content": content[:2000]}}
                            ],
                            "language": code_language,
                        },
                    }
                )
                code_mode = False
                code_content = []
                code_language = "plain text"
            else:
                # 代码块开始，提取语言标识
                code_mode = True
                lang = stripped[3:].strip().lower()
                # Notion 支持的语言列表（部分）
                supported = [
                    "python",
                    "javascript",
                    "typescript",
                    "java",
                    "c",
                    "c++",
                    "css",
                    "html",
                    "json",
                    "markdown",
                    "sql",
                    "shell",
                    "bash",
                    "ruby",
                    "go",
                    "rust",
                    "swift",
                    "kotlin",
                    "php",
                    "scala",
                    "r",
                    "matlab",
                    "plain text",
                ]
                code_language = lang if lang in supported else "plain text"
            continue

        if code_mode:
            code_content.append(line)
            continue

        # =====================
        # 2. 数学块
        # =====================
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

        # =====================
        # 3. 表格
        # =====================
        if stripped.startswith("|") and stripped.endswith("|"):
            cells: List[str] = [c.strip() for c in stripped.strip("|").split("|")]

            # 跳过分隔行 |---|---|---|
            if _is_separator_row(cells):
                continue

            table_rows.append(cells)
            continue
        else:
            # 当前行不是表格行，如果之前有积累的表格数据，flush 它
            if table_rows:
                t = _flush_table(table_rows)
                if t:
                    stack[-1]["children"].append(t)
                table_rows = []

        # =====================
        # 4. 空行跳过
        # =====================
        if not stripped:
            continue

        # =====================
        # 5. 缩进处理
        # =====================
        indent = (len(line) - len(line.lstrip())) // 2
        while len(stack) > 1 and indent <= stack[-1]["indent"]:
            stack.pop()

        new_block: Optional[Dict[str, Any]] = None
        is_container: bool = False

        # =====================
        # 6. 标题（####+ 自动降级为 heading_3）
        # =====================
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
        elif stripped.startswith("### ") or stripped.startswith("####"):
            new_block = {
                "type": "heading_3",
                "heading_3": {
                    "rich_text": parse_rich_text(re.sub(r"^#+\s+", "", stripped))
                },
            }

        # =====================
        # 7. 列表 + 引用（container，支持嵌套）
        # =====================
        elif re.match(r"^[-*]\s+", stripped):
            new_block = {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": parse_rich_text(stripped[2:])},
            }
            is_container = True

        # 🔥 新增：numbered_list_item 也是 container
        elif re.match(r"^\d+\.\s+", stripped):
            # 提取编号后的内容
            content_text = re.sub(r"^\d+\.\s+", "", stripped)
            new_block = {
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": parse_rich_text(content_text)},
            }
            is_container = True

        elif stripped.startswith("> "):
            new_block = {
                "type": "quote",
                "quote": {"rich_text": parse_rich_text(stripped[2:])},
            }
            is_container = True

        # =====================
        # 8. 分割线
        # =====================
        elif stripped in ("---", "***", "___"):
            new_block = {
                "object": "block",
                "type": "divider",
                "divider": {},
            }

        # =====================
        # 9. 默认：段落
        # =====================
        else:
            new_block = {
                "type": "paragraph",
                "paragraph": {"rich_text": parse_rich_text(stripped)},
            }

        if new_block:
            new_block["object"] = "block"
            stack[-1]["children"].append(new_block)

            # 🔥 嵌套深度限制：Notion API 最多支持 3 层子块
            # stack 长度 = 当前嵌套深度 + 1（根层）
            # 所以 len(stack) < 4 才能继续嵌套
            if is_container and len(stack) < 4:
                new_block["children"] = []
                stack.append({"children": new_block["children"], "indent": indent})

    # =====================
    # 清理残留表格（文件末尾没有空行的情况）
    # =====================
    if table_rows:
        t = _flush_table(table_rows)
        if t:
            stack[-1]["children"].append(t)

    # =====================
    # 清理空的 children 数组
    # =====================
    def _clean(blocks: List[Dict[str, Any]]) -> None:
        for b in blocks:
            if "children" in b:
                if not b["children"]:
                    del b["children"]
                else:
                    _clean(b["children"])

    _clean(root_blocks)
    return root_blocks
