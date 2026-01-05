"""
notion/block_builder.py
负责将 Markdown 文本转换为 Notion Block 格式 (纯逻辑，无网络请求)
"""
import re
from typing import List, Dict, Any, Optional

def _safe_str(val: Any) -> str:
    """安全转换为字符串并去除首尾空格"""
    if val is None: return ""
    return str(val).strip()

def parse_rich_text(text: str) -> List[Dict]:
    """解析 Markdown 行内样式 (Bold, Code, Link, Math, Highlight)"""
    if not text: return []
    rich_text = []
    # 正则：匹配 $公式$, `代码`, [链接], **加粗**, ==高亮==
    pattern = re.compile(r'(\$[^\$]+\$|`[^`]+`|\[[^\]]+\]\([^\)]+\)|\*\*[^\*]+\*\*)')
    # 注意：高亮 ==...== 的正则可以根据需要补全，这里保持你原有的逻辑结构
    
    parts = pattern.split(text)
    for part in parts:
        if not part: continue
        
        # 1. 行内公式
        if part.startswith('$') and part.endswith('$') and len(part) > 2:
            content = part[1:-1]
            rich_text.append({"type": "equation", "equation": {"expression": content}})
        # 2. 代码
        elif part.startswith('`') and part.endswith('`'):
            rich_text.append({
                "type": "text", 
                "text": {"content": part[1:-1]}, 
                "annotations": {"code": True}
            })
        # 3. 链接
        elif part.startswith('[') and ']' in part and '(' in part and part.endswith(')'):
            try:
                link_text = part[1:part.index(']')]
                link_url = part[part.index('(')+1:-1]
                rich_text.append({
                    "type": "text", 
                    "text": {"content": link_text, "link": {"url": link_url}}
                })
            except:
                rich_text.append({"type": "text", "text": {"content": part}})
        # 4. 加粗
        elif part.startswith('**') and part.endswith('**'):
            rich_text.append({
                "type": "text", 
                "text": {"content": part[2:-2]}, 
                "annotations": {"bold": True}
            })
        # 5. 普通文本
        else:
            rich_text.append({"type": "text", "text": {"content": part}})
    return rich_text

def _flush_table(table_rows: List[List[str]]) -> Optional[Dict]:
    """构建表格 Block"""
    if not table_rows: return None
    width = max(len(row) for row in table_rows) if table_rows else 0
    if width == 0: return None

    table_children = []
    for row_cells in table_rows:
        current_cells = row_cells + [""] * (width - len(row_cells))
        notion_cells = [parse_rich_text(cell) for cell in current_cells]
        table_children.append({
            "type": "table_row",
            "table_row": {"cells": notion_cells}
        })
    
    return {
        "object": "block", "type": "table",
        "table": {"table_width": width, "has_column_header": True, "children": table_children}
    }

def markdown_to_blocks(markdown_text: str) -> List[Dict]:
    """核心转换器：Markdown -> Notion Blocks"""
    blocks = []
    if not markdown_text: return blocks
    lines = markdown_text.split('\n')
    
    code_mode = False
    code_content = []
    code_lang = "plain text"
    math_mode = False
    math_content = []
    table_rows = [] 

    for line in lines:
        stripped = line.strip()
        
        # 1. 公式块 $$
        if stripped.startswith("$$"):
            if stripped.endswith("$$") and len(stripped) > 2:
                blocks.append({
                    "object": "block", "type": "equation",
                    "equation": {"expression": stripped[2:-2].strip()}
                })
                continue
            if math_mode: # 结束
                blocks.append({
                    "object": "block", "type": "equation",
                    "equation": {"expression": "\n".join(math_content)}
                })
                math_mode = False; math_content = []
            else: # 开始
                if table_rows: blocks.append(_flush_table(table_rows)); table_rows = []
                math_mode = True
            continue
        if math_mode: math_content.append(line); continue

        # 2. 代码块 ```
        if stripped.startswith("```"):
            if code_mode:
                blocks.append({
                    "object": "block", "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                        "language": code_lang
                    }
                })
                code_mode = False; code_content = []
            else:
                if table_rows: blocks.append(_flush_table(table_rows)); table_rows = []
                code_mode = True
                lang = stripped[3:].strip()
                code_lang = lang if lang else "plain text"
            continue
        if code_mode: code_content.append(line); continue

        # 3. 表格
        if stripped.startswith('|'):
            clean_cells = [c.strip() for c in stripped.strip('|').split('|')]
            if not all(re.match(r'^[-: ]+$', c) for c in clean_cells if c):
                table_rows.append(clean_cells)
            continue
        if table_rows: blocks.append(_flush_table(table_rows)); table_rows = []
        
        if not stripped: continue

        # 4. 普通 Markdown
        if stripped.startswith('# '):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": parse_rich_text(stripped[2:])}})
        elif stripped.startswith('## '):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": parse_rich_text(stripped[3:])}})
        elif stripped.startswith('### ') or stripped.startswith('#### '):
            content = stripped[4:] if stripped.startswith('### ') else stripped[5:]
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": parse_rich_text(content)}})
        elif stripped.startswith('- ') or stripped.startswith('* '):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": parse_rich_text(stripped[2:])}})
        elif re.match(r'^\d+\.\s', stripped):
            content = re.sub(r'^\d+\.\s', '', stripped, count=1)
            blocks.append({"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": parse_rich_text(content)}})
        elif stripped.startswith('> '):
            # Callout 检测
            content = stripped[2:].strip()
            callout_emojis = ["💡", "⚠️", "ℹ️", "✅", "❌", "📌", "🔥", "🧠"]
            first_char = content[0] if content else ""
            if first_char in callout_emojis:
                 blocks.append({
                    "object": "block", "type": "callout",
                    "callout": {"rich_text": parse_rich_text(content[1:].strip()), "icon": {"emoji": first_char}, "color": "gray_background"}
                })
            else:
                blocks.append({"object": "block", "type": "quote", "quote": {"rich_text": parse_rich_text(content)}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": parse_rich_text(stripped)}})

    # 收尾
    if table_rows: blocks.append(_flush_table(table_rows))
    return blocks