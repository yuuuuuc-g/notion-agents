import os
import re
import requests
from notion_client import Client
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()

# === 配置 ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
# 这里的 ID 如果不需要区分，可以在 .env 里只配一个，或者按需读取
DB_SPANISH_ID = os.environ.get("NOTION_DATABASE_ID")          
DB_HUMANITIES_ID = os.environ.get("NOTION_DATABASE_ID_HUMANITIES", DB_SPANISH_ID)  
DB_TECH_ID = os.environ.get("NOTION_DATABASE_ID_TECH", DB_SPANISH_ID)

notion = Client(auth=NOTION_TOKEN)

# ==========================================
# 🔧 核心辅助函数 (Internal Helpers)
# ==========================================

def _safe_str(val: Any) -> str:
    """安全转换为字符串并去除首尾空格"""
    if val is None: return ""
    return str(val).strip()

def parse_rich_text(text: str) -> List[Dict]:
    """
    解析 Markdown 行内样式，返回 Notion rich_text 对象数组
    支持: **Bold**, `Code`, [Link](url), $Math$
    """
    if not text: return []
    
    rich_text = []
    # 正则逻辑增强：
    # 1. 行内公式: $...$ (非贪婪匹配)
    # 2. 代码: `...`
    # 3. 链接: [...](...)
    # 4. 加粗: **...**
    pattern = re.compile(r'(\$[^\$]+\$|`[^`]+`|\[[^\]]+\]\([^\)]+\)|\*\*[^\*]+\*\*)')
    
    parts = pattern.split(text)
    
    for part in parts:
        if not part: continue
        
        # 🆕 1. 行内公式 $math$
        if part.startswith('$') and part.endswith('$') and len(part) > 2:
            content = part[1:-1]
            rich_text.append({
                "type": "equation",
                "equation": {"expression": content}
            })

        # 2. 行内代码 `code`
        elif part.startswith('`') and part.endswith('`'):
            content = part[1:-1]
            rich_text.append({
                "type": "text",
                "text": {"content": content},
                "annotations": {"code": True}
            })
            
        # 3. 链接 [text](url)
        elif part.startswith('[') and ']' in part and '(' in part and part.endswith(')'):
            try:
                link_text = part[1:part.index(']')]
                link_url = part[part.index('(')+1:-1]
                rich_text.append({
                    "type": "text",
                    "text": {
                        "content": link_text, 
                        "link": {"url": link_url}
                    }
                })
            except:
                rich_text.append({"type": "text", "text": {"content": part}})
                
        # 4. 加粗 **bold**
        elif part.startswith('**') and part.endswith('**'):
            content = part[2:-2]
            rich_text.append({
                "type": "text",
                "text": {"content": content},
                "annotations": {"bold": True}
            })
            
        # 5. 普通文本
        else:
            rich_text.append({"type": "text", "text": {"content": part}})
            
    return rich_text

def _flush_table(table_rows: List[List[str]]) -> Optional[Dict]:
    """将缓存的行数据构建为 Notion Table Block"""
    if not table_rows: return None
    
    # 确定最大列宽
    width = max(len(row) for row in table_rows) if table_rows else 0
    if width == 0: return None

    table_children = []
    for row_cells in table_rows:
        # 补齐列宽 (Notion 要求每行 cell 数量一致)
        current_cells = row_cells + [""] * (width - len(row_cells))
        
        # 构造单元格 (使用 parse_rich_text 支持单元格内的加粗等)
        notion_cells = [parse_rich_text(cell) for cell in current_cells]
        
        table_children.append({
            "type": "table_row",
            "table_row": {"cells": notion_cells}
        })
    
    return {
        "object": "block", 
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True, # 默认第一行为表头
            "children": table_children
        }
    }

def _append_children_in_batches(page_id: str, children: List[Dict]):
    """
    通用工具：解决 Notion API 单次请求最多包含 100 个 Block 的限制
    """
    if not children: return
    
    batch_size = 100
    total = len(children)
    batches = [children[i : i + batch_size] for i in range(0, total, batch_size)]
    
    print(f"📡 Uploading {total} blocks in {len(batches)} batches...")
    
    for idx, batch in enumerate(batches):
        try:
            notion.blocks.children.append(block_id=page_id, children=batch)
            print(f"   - ✅ Batch {idx + 1}/{len(batches)} uploaded.")
        except Exception as e:
            print(f"   - ❌ Batch {idx + 1} failed: {e}")
            # 可选：这里可以抛出异常或者记录日志

# ==========================================
# 📝 排版引擎 (Parsing Engine)
# ==========================================

def markdown_to_blocks(markdown_text: str) -> List[Dict]:
    """
    核心转换器：Markdown -> Notion Blocks
    支持：Headings, Lists, Quote, Code Block, Table, Rich Text, Math Block
    """
    blocks = []
    if not markdown_text: return blocks
        
    lines = markdown_text.split('\n')
    
    # --- 状态机变量 ---
    code_mode = False
    code_content = []
    code_lang = "plain text"
    
    math_mode = False  # 🆕 新增：公式块模式
    math_content = []

    table_rows = [] 

    for line in lines:
        stripped = line.strip()
        
        # ==========================
        # 🆕 1. 处理独立公式块 ($$)
        # ==========================
        if stripped.startswith("$$"):
            # 情况 A: 单行公式块 $$ E=mc^2 $$
            if stripped.endswith("$$") and len(stripped) > 2:
                expr = stripped[2:-2].strip()
                blocks.append({
                    "object": "block", "type": "equation",
                    "equation": {"expression": expr}
                })
                continue
            
            # 情况 B: 多行公式块的开始或结束
            if math_mode:
                # 结束公式块
                blocks.append({
                    "object": "block", "type": "equation",
                    "equation": {"expression": "\n".join(math_content)}
                })
                math_mode = False
                math_content = []
            else:
                # 开始公式块
                # 先结算之前的表格
                if table_rows:
                    tb = _flush_table(table_rows)
                    if tb: blocks.append(tb)
                    table_rows = []
                math_mode = True
            continue
            
        if math_mode:
            math_content.append(line) # 保留原始格式
            continue

        # ==========================
        # 2. 处理代码块 (```)
        # ==========================
        if stripped.startswith("```"):
            if code_mode:
                blocks.append({
                    "object": "block", "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                        "language": code_lang
                    }
                })
                code_mode = False
                code_content = []
            else:
                if table_rows:
                    tb = _flush_table(table_rows)
                    if tb: blocks.append(tb)
                    table_rows = []
                code_mode = True
                lang = stripped[3:].strip()
                code_lang = lang if lang else "plain text"
            continue
            
        if code_mode:
            code_content.append(line)
            continue

        # ==========================
        # 3. 处理表格 (| ... |)
        # ==========================
        if stripped.startswith('|'):
            clean_cells = [c.strip() for c in stripped.strip('|').split('|')]
            is_separator = all(re.match(r'^[-: ]+$', c) for c in clean_cells if c)
            if not is_separator:
                table_rows.append(clean_cells)
            continue
        
        if table_rows:
            tb = _flush_table(table_rows)
            if tb: blocks.append(tb)
            table_rows = []

        if not stripped: continue

        # ==========================
        # 4. 普通 Markdown 解析
        # ==========================
        
        # H1 - H3
        if stripped.startswith('# '):
            blocks.append({
                "object": "block", "type": "heading_1",
                "heading_1": {"rich_text": parse_rich_text(stripped[2:])}
            })
        elif stripped.startswith('## '):
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": parse_rich_text(stripped[3:])}
            })
        elif stripped.startswith('### '):
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": parse_rich_text(stripped[4:])}
            })
            
        # 🆕 H4 兼容 (####) -> 转为 H3
        elif stripped.startswith('#### '):
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": parse_rich_text(stripped[5:])}
            })

        # Lists
        elif stripped.startswith('- ') or stripped.startswith('* '):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": parse_rich_text(stripped[2:])}
            })
        elif re.match(r'^\d+\.\s', stripped):
            content = re.sub(r'^\d+\.\s', '', stripped, count=1)
            blocks.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": parse_rich_text(content)}
            })
            
        # Quote
        elif stripped.startswith('> '):
            blocks.append({
                "object": "block", "type": "quote",
                "quote": {"rich_text": parse_rich_text(stripped[2:])}
            })
            
        # Paragraph
        else:
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": parse_rich_text(stripped)}
            })

    # 收尾
    if table_rows:
        tb = _flush_table(table_rows)
        if tb: blocks.append(tb)
    if code_mode and code_content: # 这里只是简单兜底，不严谨但够用
        pass
    if math_mode and math_content: # 兜底公式
         blocks.append({
            "object": "block", "type": "equation",
            "equation": {"expression": "\n".join(math_content)}
        })

    return blocks

# ==========================================
# 🚀 业务逻辑操作 (Public API)
# ==========================================

def create_general_note(data: Dict, target_db_id: str, original_url: str = None) -> Optional[str]:
    """
    创建新笔记页面
    """
    title = _safe_str(data.get('title', 'Untitled'))
    summary = data.get('summary')
    markdown_body = data.get('markdown_body', '')
    
    print(f"✍️ [Notion Ops] Creating Note: {title}")
    
    # 1. 构建正文 Blocks
    children = []
    
    # A. 插入 Summary Callout (如果存在)
    if summary:
        children.append({
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": parse_rich_text(summary),
                "icon": {"emoji": "💡"}, "color": "gray_background"
            }
        })
    
    # B. 解析 Markdown 正文
    if markdown_body:
        children.extend(markdown_to_blocks(markdown_body))
    
    try:
        # Notion API 限制: 创建页面时 initial children 也不能超过 100
        # 所以我们这里只发前 100 个，剩下的用 append
        initial_batch = children[:100]
        remaining_blocks = children[100:]
        
        response = notion.pages.create(
            parent={"database_id": target_db_id},
            properties={
                "Name": {"title": [{"text": {"content": title}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
                "Type": {"select": {"name": "Article"}}, # 确保数据库有 Type 属性
                "URL": {"url": original_url if original_url else None}
            },
            children=initial_batch
        )

        page_id = response["id"]
        print(f"✅ Page Created: {page_id}")

        # 如果还有剩下的，分批追加
        if remaining_blocks:
            _append_children_in_batches(page_id, remaining_blocks)

        return page_id

    except Exception as e:
        print(f"❌ Create Failed: {e}")
        return None


def append_to_page(page_id: str, data: Dict, restore_mode: bool = False) -> bool:
    """
    向现有页面追加内容 或 覆盖重写
    :param restore_mode: True=完全重写(合并场景); False=底部追加(Update场景)
    """
    print(f"➕ [Notion Ops] Appending to {page_id} (Restore: {restore_mode})")
    
    children = []
    summary = data.get("summary")
    title = _safe_str(data.get('title', 'Update'))

    # 1. 头部构建
    if restore_mode:
        # 重写模式：加上 Summary
        if summary:
            children.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": parse_rich_text(summary),
                    "icon": {"emoji": "💡"}, "color": "gray_background"
                }
            })
    else:
        # 追加模式：加上分隔线和标题
        children.extend([
            {"object": "block", "type": "divider", "divider": {}},
            {"object": "block", "type": "heading_2", "heading_2": {
                "rich_text": [{"text": {"content": f"Update: {title}"}}], 
                "color": "blue_background"
            }}
        ])

    # 2. 正文解析
    if data.get("markdown_body"):
        children.extend(markdown_to_blocks(data["markdown_body"]))
    else:
        # 兜底纯文本
        raw = str(data.get("blocks", ""))
        children.append({
            "object": "block", "type": "paragraph", 
            "paragraph": {"rich_text": [{"text": {"content": raw}}]}
        })

    # 3. 分批写入
    try:
        _append_children_in_batches(page_id, children)
        return True
    except Exception as e:
        print(f"❌ Append Failed: {e}")
        return False


def overwrite_page_content(page_id: str, draft_data: Dict) -> bool:
    """
    覆盖页面逻辑：先清空，再写入
    """
    print(f"♻️ [Notion Ops] Overwriting page {page_id}...")
    
    try:
        # 1. 获取所有子 block
        # 注意：如果页面非常长，这里可能需要分页 list，但通常 list 默认返回 100 个
        has_more = True
        start_cursor = None
        
        while has_more:
            response = notion.blocks.children.list(block_id=page_id, start_cursor=start_cursor)
            blocks = response.get("results", [])
            
            # 2. 逐个删除 (Notion API 不支持批量删除，只能一个个删)
            for b in blocks:
                notion.blocks.delete(block_id=b["id"])
            
            has_more = response.get("has_more")
            start_cursor = response.get("next_cursor")
        
        print("   - 🗑️ Old content cleared.")

        # 3. 写入新内容 (使用 restore_mode=True)
        return append_to_page(page_id, draft_data, restore_mode=True)

    except Exception as e:
        print(f"❌ Overwrite Failed: {e}")
        return False


def get_page_text(page_id: str) -> str:
    """
    读取页面纯文本 (用于 LLM 上下文)
    """
    print(f"📖 [Notion Ops] Reading {page_id}...")
    try:
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])
        
        lines = []
        for b in blocks:
            b_type = b.get("type")
            # 提取 rich_text
            if "rich_text" in b.get(b_type, {}):
                text_objs = b[b_type]["rich_text"]
                plain = "".join([t.get("plain_text", "") for t in text_objs])
                if plain: lines.append(plain)
            
            # 提取代码
            elif b_type == "code":
                text_objs = b["code"].get("rich_text", [])
                code = "".join([t.get("plain_text", "") for t in text_objs])
                lines.append(f"```\n{code}\n```")

        return "\n\n".join(lines)
    except Exception as e:
        print(f"❌ Read Failed: {e}")
        return ""