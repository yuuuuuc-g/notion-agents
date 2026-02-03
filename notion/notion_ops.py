"""
notion/notion_ops.py
[Infrastructure Decoupling Refactored]
Notion 服务的具体实现类，支持依赖注入。
✅ 升级 v5.1: 修复嵌套写入逻辑
   - 修复浅拷贝导致 table.children 被错误提取的问题
   - 使用 copy.deepcopy 确保数据完整性
   - 统一嵌套写入策略：先写父块，再追加子块
"""

import concurrent.futures
import copy
from typing import Dict, List, Optional

import requests
from notion_client import Client

from utils.logger import get_logger

from .block_builder import markdown_to_blocks
from .notion_interface import INotionService

logger = get_logger(__name__)


class NotionService(INotionService):
    """
    Notion 服务类，封装了所有与 Notion API 相关的操作。
    """

    def __init__(self, token: str, default_db_id: str):
        if not token:
            raise ValueError("❌ Notion Token 不能为空")

        self.token = token
        self.notion = Client(auth=token)
        self.default_db_id = default_db_id

    # ==========================================
    # 🔥 核心修复：_append_children_in_batches
    # ==========================================
    # Notion API 的严格规则：
    #   blocks.children.append 的 children 参数，
    #   每个 block 内部不能再嵌套 children（除了 table 的 table_row）
    #
    # 正确的写入策略：
    #   Step 1: 写入当前层级的所有 block（去掉 children）
    #   Step 2: 拿到 Step 1 返回的 block ID
    #   Step 3: 对每个有子块的 block，递归执行 Step 1-3
    #
    # 特殊类型：
    #   table: children 是 table_row，必须随 table 一起写入
    #         不能单独追加，否则 API 报错
    # ==========================================

    def _append_children_in_batches(self, parent_id: str, children: List[Dict]):
        if not children:
            return

        batch_size = 50
        for i in range(0, len(children), batch_size):
            batch = children[i : i + batch_size]

            # 🔥 key fix: 用 deepcopy，避免浅拷贝修改原始数据
            batch = copy.deepcopy(batch)

            sub_children_map = {}  # {batch_index: [sub_blocks]}
            clean_batch = []

            for idx, block in enumerate(batch):
                b_type = block.get("type")

                # 🔥 table 类型：children 是 table_row，必须保留
                # Notion API 要求 table 和 table_row 一起写入
                if b_type == "table":
                    clean_batch.append(block)
                    continue

                # 其他类型：提取 children，后续单独追加
                extracted = None

                # 检查两种可能的 children 位置
                if b_type and "children" in block.get(b_type, {}):
                    extracted = block[b_type].pop("children")
                elif "children" in block:
                    extracted = block.pop("children")

                if extracted:
                    sub_children_map[idx] = extracted

                clean_batch.append(block)

            try:
                response = self.notion.blocks.children.append(
                    block_id=parent_id, children=clean_batch
                )
                results = response.get("results", [])

                # 递归追加子块
                for batch_idx, sub_blocks in sub_children_map.items():
                    if batch_idx < len(results):
                        new_parent_id = results[batch_idx]["id"]
                        self._append_children_in_batches(new_parent_id, sub_blocks)
                    else:
                        logger.warning(
                            f"⚠️ [Notion] 子块追加跳过: batch_idx={batch_idx}, "
                            f"results_len={len(results)}"
                        )

            except Exception as e:
                logger.error(f"❌ 追加 Block 失败: {e}")
                raise e

    # ==========================================
    # fetch_database_content（保持不变）
    # ==========================================
    def fetch_database_content(self, db_id: Optional[str] = None) -> List[Dict]:
        target_db = db_id if db_id else self.default_db_id
        if not target_db:
            logger.error("❌ 未提供 Database ID")
            return []

        clean_db_id = target_db.replace("-", "")
        token = self.token

        logger.info(f"🔍 [Standard Sync] 正在拉取数据库: {target_db}")

        url = f"https://api.notion.com/v1/databases/{clean_db_id}/query"
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

        pages_data = []
        has_more = True
        next_cursor = None

        try:
            while has_more:
                payload = {}
                if next_cursor:
                    payload["start_cursor"] = next_cursor

                response = requests.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(
                        f"❌ Notion API 报错 (Status {response.status_code}): {response.text}"
                    )
                    break

                data = response.json()
                results = data.get("results", [])
                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor")

                for page in results:
                    page_id = page["id"]
                    properties = page.get("properties", {})

                    title = "Untitled"
                    for prop in properties.values():
                        if isinstance(prop, dict) and prop.get("type") == "title":
                            title_objs = prop.get("title", [])
                            if title_objs:
                                title = title_objs[0].get("plain_text", "Untitled")
                            break

                    content = self.get_page_text(page_id)
                    if content.strip():
                        pages_data.append(
                            {"id": page_id, "title": title, "content": content}
                        )

            return pages_data

        except Exception as e:
            logger.error(f"❌ 数据库拉取通讯失败: {e}")
            raise e

    # ==========================================
    # create_page（v5.1 版本，带 Type + Tags）
    # ==========================================
    def create_page(
        self,
        title: str,
        children: List[Dict],
        icon: str = "📄",
        db_id: str = None,
        category: str = None,
        tags: List[str] = None,
    ) -> Dict:
        target_db = db_id if db_id else self.default_db_id
        if not target_db:
            raise ValueError("❌ 未配置有效的 Database ID")

        logger.info(f"✍️ [Notion] 创建页面: {title} (分类: {category})")

        try:
            # 构建 properties
            properties = {"Name": {"title": [{"text": {"content": title}}]}}

            if category:
                properties["Type"] = {"select": {"name": category}}

            if tags and isinstance(tags, list):
                properties["Tags"] = {"multi_select": [{"name": tag} for tag in tags]}

            # 创建空页面
            response = self.notion.pages.create(
                parent={"database_id": target_db},
                icon={"type": "emoji", "emoji": icon},
                properties=properties,
                children=[],
            )
            page_id = response["id"]
            logger.info(f"✅ [Notion] 页面创建成功: {page_id}")

            # 追加内容（使用修复后的方法）
            if children:
                try:
                    self._append_children_in_batches(page_id, children)
                    logger.info(f"✅ [Notion] 内容追加成功 ({len(children)} blocks)")
                except Exception as inner_e:
                    logger.error("⚠️ 内容追加失败，执行回滚...")
                    self.delete_page(page_id)
                    raise inner_e

            return response

        except Exception as e:
            logger.error(f"❌ 页面任务失败: {e}")
            raise e

    # ==========================================
    # delete_page, get_page_text, overwrite（保持不变）
    # ==========================================
    def delete_page(self, page_id: str) -> bool:
        try:
            self.notion.pages.update(page_id=page_id, archived=True)
            return True
        except Exception as e:
            logger.error(f"❌ 删除页面失败: {e}")
            return False

    def get_page_text(self, page_id: str) -> str:
        try:
            response = self.notion.blocks.children.list(block_id=page_id)
            blocks = response.get("results", [])
            lines = []
            for b in blocks:
                b_type = b.get("type")
                if b_type and "rich_text" in b.get(b_type, {}):
                    text_objs = b[b_type]["rich_text"]
                    plain = "".join([t.get("plain_text", "") for t in text_objs])
                    if plain:
                        lines.append(plain)
                elif b_type == "code":
                    text_objs = b["code"].get("rich_text", [])
                    code = "".join([t.get("plain_text", "") for t in text_objs])
                    lines.append(f"```\n{code}\n```")
                elif b_type == "table":
                    # 🔥 table 的文本提取
                    table_rows = b.get("table", {}).get("children", [])
                    for row in table_rows:
                        cells = row.get("table_row", {}).get("cells", [])
                        cell_texts = []
                        for cell in cells:
                            cell_text = "".join(
                                [rt.get("plain_text", "") for rt in cell]
                            )
                            cell_texts.append(cell_text)
                        lines.append(" | ".join(cell_texts))
            return "\n\n".join(lines)
        except Exception as e:
            logger.error(f"❌ 读取内容失败: {e}")
            return ""

    def _delete_block_worker(self, block_id: str):
        try:
            self.notion.blocks.delete(block_id=block_id)
        except Exception:
            pass

    def overwrite_page_content(
        self, page_id: str, markdown_body: str, summary: str = None
    ) -> bool:
        logger.info(f"♻️ 重写页面: {page_id}")
        try:
            all_block_ids = []
            has_more = True
            start_cursor = None
            while has_more:
                res = self.notion.blocks.children.list(
                    block_id=page_id, start_cursor=start_cursor
                )
                all_block_ids.extend([b["id"] for b in res.get("results", [])])
                has_more = res.get("has_more")
                start_cursor = res.get("next_cursor")

            if all_block_ids:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    executor.map(self._delete_block_worker, all_block_ids)

            new_children = markdown_to_blocks(markdown_body)
            self._append_children_in_batches(page_id, new_children)
            return True
        except Exception as e:
            logger.error(f"❌ 覆盖失败: {e}")
            return False

    # ==========================================
    # 🔥 外科手术式操作（保持不变）
    # ==========================================
    def get_page_structure(self, page_id: str) -> List[Dict]:
        logger.info(f"🔍 [Surgical] 扫描页面结构: {page_id}")
        blocks = []
        has_more = True
        start_cursor = None

        try:
            while has_more:
                res = self.notion.blocks.children.list(
                    block_id=page_id, start_cursor=start_cursor
                )
                for b in res["results"]:
                    b_type = b["type"]
                    content = ""
                    if "rich_text" in b.get(b_type, {}):
                        content = "".join(
                            [t["plain_text"] for t in b[b_type]["rich_text"]]
                        )
                    if content:
                        blocks.append(
                            {
                                "block_id": b["id"],
                                "type": b_type,
                                "content_preview": content[:200],
                            }
                        )
                has_more = res["has_more"]
                start_cursor = res["next_cursor"]
            return blocks
        except Exception as e:
            logger.error(f"❌ 结构扫描失败: {e}")
            return []

    def update_block_text(self, block_id: str, new_text: str):
        logger.info(f"🔪 [Surgical] 更新 Block {block_id}...")
        try:
            self.notion.blocks.update(
                block_id=block_id,
                paragraph={"rich_text": [{"text": {"content": new_text}}]},
            )
            logger.info("✅ Block 已更新")
            return True
        except Exception as e:
            logger.error(f"❌ 更新失败: {e}")
            return False

    def insert_blocks_after(
        self, parent_id: str, after_block_id: str, content_markdown: str
    ):
        logger.info(f"💉 [Surgical] 在 {after_block_id} 后插入内容...")
        try:
            new_blocks = markdown_to_blocks(content_markdown)
            self.notion.blocks.children.append(
                block_id=parent_id, children=new_blocks, after=after_block_id
            )
            logger.info("✅ 内容插入成功")
            return True
        except Exception as e:
            logger.error(f"❌ 插入失败: {e}")
            return False
