import os
import requests
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

# === 配置 ===
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DB_SPANISH_ID = os.environ.get("NOTION_DATABASE_ID")          
DB_HUMANITIES_ID = os.environ.get("NOTION_DATABASE_ID_HUMANITIES")  
DB_TECH_ID = os.environ.get("NOTION_DATABASE_ID_TECH")

notion = Client(auth=NOTION_TOKEN)

# --- 核心工具：排版引擎 ---
def chunk_text(text, max_len=1900):
    """辅助函数：将长文本切分为符合 Notion 限制的片段"""
    if not text: return []
    return [text[i:i+max_len] for i in range(0, len(text), max_len)]

def clean_text(text):
    """
    清洗文本：彻底去除 Markdown 行内符号 (***, **, *, `)
    """
    if text is None: return ""
    text = str(text)
    
    # 1. 暴力去除所有星号 * (解决 ***, **, *)
    text = text.replace("*", "")
    
    # 2. 去除反引号 `
    text = text.replace("`", "")
    
    # 3. 去除行首可能残留的 "- " (如果之前解析漏了)
    if text.strip().startswith("- "):
        text = text.strip()[2:]
        
    return text.strip()

def markdown_to_blocks(markdown_text):
    """
    将 Markdown 文本转换为 Notion Blocks 结构
    支持：H1-H3, 列表, 引用, 代码块, 以及表格
    """
    blocks = []
    if not markdown_text:
        return blocks
        
    lines = markdown_text.split('\n')
    
    # 状态标记
    code_mode = False
    code_content = []
    
    table_mode = False
    table_rows = [] # 暂存表格行数据

    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # ====================
        # 1. 处理代码块 (```)
        # ====================
        if stripped.startswith("```"):
            # 如果正在录入表格，先强制结束表格
            if table_mode:
                if table_rows:
                    # 计算列数 (以第一行为准)
                    width = len(table_rows[0])
                    table_children = []
                    for row_cells in table_rows:
                        # 补齐或截断单元格以匹配宽度 (Notion要求每行单元格数一致)
                        current_cells = row_cells[:width] + [""] * (width - len(row_cells))
                        # 构建单元格对象
                        notion_cells = [[{"type": "text", "text": {"content": cell}}] for cell in current_cells]
                        table_children.append({
                            "type": "table_row",
                            "table_row": {"cells": notion_cells}
                        })
                    
                    blocks.append({
                        "object": "block", "type": "table",
                        "table": {
                            "table_width": width,
                            "has_column_header": True, # 默认第一行是表头
                            "has_row_header": False,
                            "children": table_children
                        }
                    })
                table_mode = False
                table_rows = []

            if code_mode:
                blocks.append({
                    "object": "block", "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                        "language": "plain text"
                    }
                })
                code_mode = False
                code_content = []
            else:
                code_mode = True
            continue
            
        if code_mode:
            code_content.append(line)
            continue

        # ====================
        # 2. 处理表格 (|)
        # ====================
        # 判定是否是表格行：以 | 开头 并 以 | 结尾 (宽松一点，至少包含 |)
        if stripped.startswith('|'):
            table_mode = True
            # 解析单元格：去除首尾 |，然后按 | 分割
            # 例子: "| A | B |" -> " A | B " -> [" A ", " B "]
            raw_cells = stripped.strip('|').split('|')
            clean_cells = [clean_text(c) for c in raw_cells]
            
            # 检查是否是分隔线 (如 |---|---| )，如果是则跳过
            is_separator = True
            for cell in clean_cells:
                if any(c not in '-: ' for c in cell): # 如果包含除了 - : 空格 以外的字符，就不是分隔线
                    is_separator = False
                    break
            
            if not is_separator:
                table_rows.append(clean_cells)
            continue
        
        # 如果当前行不是表格，但之前在录入表格 -> 结算表格
        if table_mode:
            if table_rows:
                width = len(table_rows[0])
                table_children = []
                for row_cells in table_rows:
                    # 补齐列宽
                    current_cells = row_cells[:width] + [""] * (width - len(row_cells))
                    notion_cells = [[{"type": "text", "text": {"content": cell}}] for cell in current_cells]
                    table_children.append({
                        "type": "table_row",
                        "table_row": {"cells": notion_cells}
                    })
                
                blocks.append({
                    "object": "block", "type": "table",
                    "table": {
                        "table_width": width,
                        "has_column_header": True,
                        "has_row_header": False,
                        "children": table_children
                    }
                })
            table_mode = False
            table_rows = []

        # 空行跳过
        if not stripped:
            continue

        # ====================
        # 3. 普通 Markdown 转换
        # ====================
        if stripped.startswith('# '):
            content = clean_text(stripped[2:])
            blocks.append({
                "object": "block", "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        elif stripped.startswith('## '):
            content = clean_text(stripped[3:])
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        elif stripped.startswith('### '):
            content = clean_text(stripped[4:])
            blocks.append({
                "object": "block", "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        elif stripped.startswith('- ') or stripped.startswith('* '):
            content = clean_text(stripped[2:])
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        elif stripped[0].isdigit() and stripped[1:3] == '. ':
            try:
                content = clean_text(stripped.split('. ', 1)[1])
            except:
                content = clean_text(stripped)
            blocks.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        elif stripped.startswith('> '):
            content = clean_text(stripped[2:])
            blocks.append({
                "object": "block", "type": "quote",
                "quote": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })
        else:
            # 普通段落
            content = clean_text(stripped)
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}
            })

    # ====================
    # 循环结束后，检查是否还有未结算的表格或代码块
    # ====================
    if table_mode and table_rows:
        width = len(table_rows[0])
        table_children = []
        for row_cells in table_rows:
            current_cells = row_cells[:width] + [""] * (width - len(row_cells))
            notion_cells = [[{"type": "text", "text": {"content": cell}}] for cell in current_cells]
            table_children.append({
                "type": "table_row",
                "table_row": {"cells": notion_cells}
            })
        blocks.append({
            "object": "block", "type": "table",
            "table": {
                "table_width": width,
                "has_column_header": True,
                "children": table_children
            }
        })
        
    if code_mode and code_content:
        blocks.append({
            "object": "block", "type": "code",
            "code": {
                "rich_text": [{"type": "text", "text": {"content": "\n".join(code_content)}}],
                "language": "plain text"
            }
        })
            
    return blocks


def build_content_blocks(summary, blocks):
    print(f"🧐 [Debug] Input blocks count: {len(blocks) if blocks else 0}")
    # print(f"🧐 [Debug] Input blocks sample: {str(blocks)[:300]}...") 

    children = []

    # 1. 添加 Summary
    if summary:
        children.append({
            "object": "block", "type": "callout",
            "callout": {
                "rich_text": [{"text": {"content": clean_text(summary)}}],
                "icon": {"emoji": "💡"}, "color": "gray_background"
            }
        })

    # 2. 兜底：纯字符串
    if isinstance(blocks, str) and blocks.strip():
        print("🧐 [Debug] Blocks is a string, converting to paragraph.")
        chunks = chunk_text(clean_text(blocks))
        for chunk in chunks:
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
            })
        return children

    # 3. 兜底：非列表
    if blocks and not isinstance(blocks, list):
        print("🧐 [Debug] Blocks is unknown type, forcing string conversion.")
        chunks = chunk_text(clean_text(str(blocks)))
        for chunk in chunks:
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
            })
        return children

    # 4. 遍历 List
    for i, block in enumerate(blocks):
        # 情况 A: 列表里是纯字符串 ["段落1", "段落2"]
        if isinstance(block, str):
            children.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": clean_text(block)}}]}
            })
            continue

        # 情况 B: 字典结构
        b_type = block.get('type')
        content = block.get('content')
        
        # 🟢【Debug】看看当前 block 是什么类型
        print(f"   - Processing Block {i}: type='{b_type}'")

        # --- 匹配逻辑 ---

        # 1. 标题 (兼容 heading, heading_1, heading_2, heading_3)
        if b_type in ['heading', 'heading_1', 'heading_2', 'heading_3']:
            children.append({
                "object": "block", "type": "heading_2", # 统一转为二级标题
                "heading_2": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })
        
        # 2. 正文 (text, paragraph)
        elif b_type in ['text', 'paragraph']:
            chunks = chunk_text(clean_text(content))
            for chunk in chunks:
                children.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": chunk}}]}
                })

        # 3. 无序列表 (bulleted_list_item) - 新 Agent 逻辑
        elif b_type == 'bulleted_list_item':
             children.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })

        # 4. 有序列表 (numbered_list_item) - 预留
        elif b_type == 'numbered_list_item':
             children.append({
                "object": "block", "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"text": {"content": clean_text(content)}}]}
            })

        # 5. 代码块 (code) - 预留
        elif b_type == 'code':
            children.append({
                "object": "block", "type": "code",
                "code": {
                    "rich_text": [{"text": {"content": str(content)}}],
                    "language": "plain text"
                }
            })
            
        # 6. 旧逻辑兼容：整个列表 (list)
        elif b_type == 'list':
            if isinstance(content, list):
                for item in content:
                    children.append({
                        "object": "block", "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": [{"text": {"content": clean_text(item)}}]}
                    })
        
        # 7. 表格 (table)
        elif b_type == 'table':
            # (简化的 table 处理，防止出错)
            pass 

        # 8. 兜底 (Else)
        else:
            print(f"⚠️ [Warn] Unknown block type: '{b_type}'. Fallback to text.")
            raw_content = content if content else str(block)
            chunks = chunk_text(clean_text(str(raw_content)))
            for chunk in chunks:
                children.append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": f"[{b_type or 'Raw'}] {chunk}"}}]}
                })

    print(f"✅ [Debug] Final children count to Notion: {len(children)}")
    return children

# --- 功能函数 (保持不变) ---
def get_all_page_titles(db_id):
    if not db_id: return []
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    headers = {"Authorization": f"Bearer {NOTION_TOKEN}", "Notion-Version": "2022-06-28", "Content-Type": "application/json"}
    try:
        response = requests.post(url, headers=headers, json={"page_size": 100}, timeout=10)
        data = response.json()
        results = []
        for page in data.get("results", []):
            try:
                props = page.get("properties", {})
                title_prop = next((v for k, v in props.items() if v["type"] == "title"), None)
                if title_prop and title_prop.get("title"):
                    title_text = "".join([t["plain_text"] for t in title_prop["title"]])
                    if title_text: results.append({"id": page["id"], "title": title_text})
            except: continue
        return results
    except Exception as e:
        print(f"❌ Error fetching titles: {e}")
        return []

def get_page_structure(page_id):
    try:
        blocks = notion.blocks.children.list(block_id=page_id).get("results", [])
        structure_desc = []
        tables = []
        for b in blocks:
            if b["type"] == "heading_2":
                text = b["heading_2"]["rich_text"][0]["plain_text"] if b["heading_2"]["rich_text"] else ""
                structure_desc.append(f"[Heading] {text}")
            elif b["type"] == "table":
                tables.append({"id": b["id"], "desc": "Existing Table"})
                structure_desc.append(f"[Table] ID:{b['id']}")
        return "\n".join(structure_desc), tables
    except: return "", []

# --- 核心操作 ---

def create_general_note(data: dict, target_db_id: str, original_url: str = None) -> str:
    """
    在指定的 Notion 数据库中创建通用笔记
    
    参数:
        data: 笔记数据字典，包含 title, summary, markdown_body 或 blocks, tags
        target_db_id: 目标数据库 ID
        original_url: 原始 URL（可选）
    
    返回:
        str: 创建的页面 ID，失败返回 None
    """
    title = data.get('title', 'Unnamed')
    clean_title = clean_text(title)
    summary = data.get('summary')
    
    print(f"✍️ Creating General Note: {clean_title}...")
    
    # 优先检查是否使用了 Markdown 格式
    if 'markdown_body' in data and data['markdown_body']:
        print("📝 Detected Markdown content. Converting...")
        # 1. 先生成 Markdown 转换后的 Blocks
        content_blocks = markdown_to_blocks(data['markdown_body'])
        
        # 2. 手动把 Summary 加在最前面 (Callout 样式)
        children = []
        if summary:
            children.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": [{"text": {"content": clean_text(summary)}}],
                    "icon": {"emoji": "💡"}, "color": "gray_background"
                }
            })
        children.extend(content_blocks)
        
    else:
        # 回退逻辑：如果没有 Markdown，使用旧格式 (build_content_blocks)
        blocks = data.get('blocks') or data.get('key_points', []) 
        children = build_content_blocks(summary, blocks)

        if not data.get('blocks') and blocks:
            children.insert(1, {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📝 Key Takeaways"}}], "color": "blue"}})

    try:
        if not target_db_id:
            print("❌ Error: Target DB ID is missing.")
            return None

        # === Notion block limit handling (≤100 per request) ===
        batch_size = 100
        first_batch = children[:batch_size]
        remaining_batches = [
            children[i:i + batch_size]
            for i in range(batch_size, len(children), batch_size)
        ]

        # 1️⃣ Create page with first batch
        response = notion.pages.create(
            parent={"database_id": target_db_id},
            properties={
                "Name": {"title": [{"text": {"content": clean_title}}]},
                "Tags": {"multi_select": [{"name": tag} for tag in data.get('tags', [])]},
                "Type": {"select": {"name": "Article"}},
                "URL": {"url": original_url if original_url else None}
            },
            children=first_batch
        )

        page_id = response["id"]
        print("✅ General Note Created with first block batch!")

        # 2️⃣ Append remaining batches (if any)
        for idx, batch in enumerate(remaining_batches):
            notion.blocks.children.append(
                block_id=page_id,
                children=batch
            )
            print(f"   - Appended batch {idx + 2}/{len(remaining_batches) + 1}")

        print("✅ General Note Fully Written with chunked blocks!")
        return page_id

    except Exception as e:
        print(f"❌ Failed: {e}")
        return None


def append_to_page(page_id: str, data: dict, restore_mode: bool = False) -> bool:
    """
    向页面追加内容或覆盖重写内容
    
    参数:
        page_id: Notion 页面 ID
        data: 内容数据字典，包含 title, summary, markdown_body 或 blocks
        restore_mode: 如果为 True，表示覆盖重写操作（不加分割线和 Update 标题）
                     如果为 False，表示追加操作（添加分割线和 Update 标题）
    
    返回:
        bool: 成功返回 True，失败返回 False
    """
    print(f"➕ Appending content to page {page_id} (Restore Mode: {restore_mode})...")
    
    children = []

    # ==================================================
    # 1. 头部处理 (Header Logic)
    # ==================================================
    if restore_mode:
        # 模式 A: 覆盖重写 (像一篇新文章)
        # 1.1 恢复 Summary Callout
        summary = data.get("summary")
        if summary:
            children.append({
                "object": "block", "type": "callout",
                "callout": {
                    "rich_text": [{"text": {"content": clean_text(summary)}}],
                    "icon": {"emoji": "💡"}, "color": "gray_background"
                }
            })
        # 覆盖模式下，不需要 "Update: Title" 这种标题，因为 Notion 页面本身有标题属性
    else:
        # 模式 B: 底部追加 (Append)
        # 1.2 添加分割线和 Update 标题
        update_title = data.get('title', 'New Update')
        children.extend([
            {"object": "block", "type": "divider", "divider": {}},
            {"object": "block", "type": "heading_2", "heading_2": {
                "rich_text": [{"text": {"content": f"Update: {update_title}"}}], 
                "color": "blue_background"
            }}
        ])

    # 2. 解析正文 (核心逻辑)
    content_blocks = []
    
    if data.get("markdown_body"):    #  优先使用 Markdown (这是新 Agent 的主力格式)
        print("📝 Converting Markdown body to blocks...")
        content_blocks = markdown_to_blocks(data["markdown_body"])
        
    elif data.get("blocks"):         #  兼容旧格式 (如果 data 里只有 blocks)
        print("🧱 Using legacy blocks format...")
        content_blocks = build_content_blocks(data.get("summary", ""), data["blocks"])
        
    else:                            #  兜底 (只有纯文本)
        print("📄 Using raw text fallback...")
        raw_text = str(data)
        content_blocks = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": raw_text}}]}}]

    # 3. 合并 Header 和 Content
    children.extend(content_blocks)

    if not children:
        print("⚠️ Nothing to append.")
        return False

    # 4. 调用 API (分批处理，因为 Notion 一次限制 100 个 block)
    try:
        batch_size = 100
        total_batches = (len(children) + batch_size - 1) // batch_size
        
        for i in range(0, len(children), batch_size):
            batch = children[i:i + batch_size]
            notion.blocks.children.append(block_id=page_id, children=batch)
            print(f"   - Batch {i//batch_size + 1}/{total_batches} appended.")
            
        print("✅ Content updated successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Append failed: {e}")
        return False

def add_row_to_table(table_id, row_data):
    print(f"➕ Inserting row into table {table_id}...")
    try:
        row_cells = [[{"text": {"content": clean_text(str(cell))}}] for cell in row_data]
        notion.blocks.children.append(
            block_id=table_id,
            children=[{"object": "block", "type": "table_row", "table_row": {"cells": row_cells}}]
        )
        print("✅ Row inserted!")
        return True
    except Exception as e:
        print(f"❌ Table insert failed: {e}")
        return False
    

def get_page_text(page_id: str) -> str:
    """
    读取 Notion 页面内容，转换为纯文本，供 LLM 参考
    
    参数:
        page_id: Notion 页面 ID
    
    返回:
        str: 页面的纯文本内容（失败返回空字符串）
    
    注意：为了节省 Token，这里只读取文本类 Block，忽略图片/表格的复杂结构
    """
    print(f"📖 Reading content from page {page_id}...")
    try:
        # 获取所有 block
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])
        
        full_text = []
        for b in blocks:
            b_type = b.get("type")
            # 提取 rich_text 里的内容
            if b_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "quote", "callout"]:
                rich_text = b.get(b_type, {}).get("rich_text", [])
                text = "".join([t.get("plain_text", "") for t in rich_text])
                if text:
                    full_text.append(text)
            
            # 简单处理代码块
            elif b_type == "code":
                rich_text = b.get("code", {}).get("rich_text", [])
                code = "".join([t.get("plain_text", "") for t in rich_text])
                full_text.append(f"```\n{code}\n```")

        return "\n\n".join(full_text)
    except Exception as e:
        print(f"❌ Failed to read page: {e}")
        return ""

def overwrite_page_content(page_id: str, draft_data: dict) -> bool:
    """
    覆盖页面内容：清空页面当前内容，并写入融合后的新内容
    
    参数:
        page_id: Notion 页面 ID
        draft_data: 草稿数据字典，包含 title, summary, markdown_body 等
    
    返回:
        bool: 成功返回 True，失败返回 False
    """
    print(f"♻️ Overwriting page {page_id} with merged content...")
    
    try:
        # 1. 获取当前所有 block ID
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])
        
        # 2. 逐个删除
        for b in blocks:
            try:
                notion.blocks.delete(block_id=b["id"])
            except:
                pass
        
        print("   - Old content cleared.")

        # 3. 写入新内容 (关键修改：开启 restore_mode)
        # 这样就会带上 Summary，且没有 "Update" 标题
        return append_to_page(page_id, draft_data, restore_mode=True)

    except Exception as e:
        print(f"❌ Overwrite failed: {e}")
        return False