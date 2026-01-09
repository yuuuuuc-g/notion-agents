"""
notion/block_builder.py
Markdown -> Notion Blocks 转换器
👉 核心修复：
1. Quote 不再作为容器 (Flatten)，消除嵌套隐患
2. Rich Text 解析增加防御，防止生成空对象导致 Block 失效
3. 严格的空 children 清理
"""
import re
from typing import List, Dict, Any, Optional

def _safe_str(val: Any) -> str:
    if val is None: return ""
    return str(val).strip()

def parse_rich_text(text: str) -> List[Dict]:
    """解析 Markdown 行内样式"""
    if not text: return []
    rich_text = []
    
    pattern = re.compile(
        r'(`[^`]+`|\$[^\$]+\$|\[[^\]]+\]\([^\)]+\)|\*\*.+?\*\*|\*[^\*]+\*|~[^~]+~)'
    )
    
    parts = pattern.split(text)
    
    for part in parts:
        if not part: continue
        
        # 统一构建函数，减少重复代码
        def add_text(content, annotations=None, url=None):
            if not content: return # 禁止空内容
            obj = {"type": "text", "text": {"content": content}}
            if url: obj["text"]["link"] = {"url": url}
            if annotations: obj["annotations"] = annotations
            rich_text.append(obj)

        if part.startswith('$') and part.endswith('$') and len(part) > 2:
            rich_text.append({"type": "equation", "equation": {"expression": part[1:-1]}})
        elif part.startswith('`') and part.endswith('`'):
            add_text(part[1:-1], {"code": True})
        elif part.startswith('[') and part.endswith(')') and '](' in part:
            try:
                split_idx = part.rindex('](') 
                link_text = part[1:split_idx]
                link_url = part[split_idx+2:-1].strip()
                if link_url:
                    add_text(link_text, url=link_url)
                else:
                    add_text(part)
            except:
                add_text(part)
        elif part.startswith('**') and part.endswith('**') and len(part) > 4:
            add_text(part[2:-2], {"bold": True})
        elif part.startswith('*') and part.endswith('*') and len(part) > 2:
            add_text(part[1:-1], {"italic": True})
        elif part.startswith('~') and part.endswith('~') and len(part) > 2:
            add_text(part[1:-1], {"strikethrough": True})
        else:
            add_text(part)
            
    # 🔥 最后的防线：如果解析结果为空，返回一个空空格，防止 Notion 报错
    if not rich_text:
        return [{"type": "text", "text": {"content": " "}}]
        
    return rich_text

def _flush_table(table_rows: List[List[str]]) -> Optional[Dict]:
    if not table_rows: return None
    width = max(len(row) for row in table_rows) if table_rows else 0
    if width == 0: return None
    table_children = []
    for row_cells in table_rows:
        current_cells = row_cells + [""] * (width - len(row_cells))
        notion_cells = [parse_rich_text(cell) for cell in current_cells]
        table_children.append({"type": "table_row", "table_row": {"cells": notion_cells}})
    return {"object": "block", "type": "table", "table": {"table_width": width, "has_column_header": True, "children": table_children}}

def markdown_to_blocks(markdown_text: str) -> List[Dict]:
    if not markdown_text: return []
    lines = markdown_text.split('\n')
    
    code_mode = False; code_content = []; code_lang = "plain text"
    math_mode = False; math_content = []
    table_rows = [] 
    
    root_blocks = []
    stack = [{"children": root_blocks, "indent": -1, "type": "root"}]

    for line in lines:
        original_line = line
        stripped = line.strip()
        
        if not stripped:
            if code_mode: code_content.append("")
            if math_mode: math_content.append("")
            continue

        indent_spaces = len(original_line) - len(original_line.lstrip(' '))
        current_indent = indent_spaces // 2

        # --- Special Blocks ---
        if stripped.startswith("$$"):
            if stripped.endswith("$$") and len(stripped) > 2:
                stack[-1]["children"].append({"object": "block", "type": "equation", "equation": {"expression": stripped[2:-2].strip()}})
                continue
            if math_mode:
                stack[-1]["children"].append({"object": "block", "type": "equation", "equation": {"expression": "\n".join(math_content)}})
                math_mode = False; math_content = []
            else:
                if table_rows: t = _flush_table(table_rows); stack[-1]["children"].append(t) if t else None; table_rows = []
                math_mode = True
            continue
        if math_mode: math_content.append(line); continue

        if stripped.startswith("```"):
            if code_mode:
                stack[-1]["children"].append({"object": "block", "type": "code", "code": {"rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}], "language": code_lang}})
                code_mode = False; code_content = []
            else:
                if table_rows: t = _flush_table(table_rows); stack[-1]["children"].append(t) if t else None; table_rows = []
                code_mode = True; lang = stripped[3:].strip(); code_lang = lang if lang else "plain text"
            continue
        if code_mode: code_content.append(line); continue

        if stripped.startswith('|'):
            clean_cells = [c.strip() for c in stripped.strip('|').split('|')]
            if not all(re.match(r'^[-: ]+$', c) for c in clean_cells if c): table_rows.append(clean_cells)
            continue
        if table_rows: t = _flush_table(table_rows); stack[-1]["children"].append(t) if t else None; table_rows = []

        # --- Nested Logic ---
        while len(stack) > 1 and current_indent <= stack[-1]["indent"]:
            stack.pop()
            
        parent_list = stack[-1]["children"]
        is_container = False 
        
        if stripped.startswith('# '):
            new_block = {"object": "block", "type": "heading_1", "heading_1": {"rich_text": parse_rich_text(stripped[2:])}}
        elif stripped.startswith('## '):
            new_block = {"object": "block", "type": "heading_2", "heading_2": {"rich_text": parse_rich_text(stripped[3:])}}
        elif stripped.startswith('### ') or stripped.startswith('#### '):
            content = stripped[4:] if stripped.startswith('### ') else stripped[5:]
            new_block = {"object": "block", "type": "heading_3", "heading_3": {"rich_text": parse_rich_text(content)}}
        elif stripped.startswith('- ') or stripped.startswith('* '):
            new_block = {"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": parse_rich_text(stripped[2:])}}
            is_container = True
        elif re.match(r'^\d+\.\s', stripped):
            content = re.sub(r'^\d+\.\s', '', stripped, count=1)
            new_block = {"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": parse_rich_text(content)}}
            is_container = True
        elif stripped.startswith('> '):
            # 🔥 降级: Quote 设为 False，彻底防止嵌套导致的 API 报错
            content = stripped[2:].strip()
            new_block = {"object": "block", "type": "quote", "quote": {"rich_text": parse_rich_text(content)}}
            is_container = False 
        else:
            new_block = {"object": "block", "type": "paragraph", "paragraph": {"rich_text": parse_rich_text(stripped)}}
            is_container = False

        parent_list.append(new_block)

        if is_container:
            new_block["children"] = []
            stack.append({"children": new_block["children"], "indent": current_indent})

    if table_rows: t = _flush_table(table_rows); stack[-1]["children"].append(t) if t else None
        
    def _clean_empty_children(blocks_list):
        for block in blocks_list:
            if "children" in block:
                if not block["children"]: del block["children"]
                else: _clean_empty_children(block["children"])
    
    _clean_empty_children(root_blocks)
    return root_blocks