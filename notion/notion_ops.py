"""
notion/notion_ops.py
[Infrastructure Decoupling Refactored]
Notion 服务的具体实现类，支持依赖注入。
✅ 修正版 v2: 回退到 requests 方式拉取数据 (最稳妥)，但修复 Token 读取逻辑
"""

import concurrent.futures
from typing import Dict, List, Optional

import requests  # 恢复 requests 库的使用
from notion_client import Client

from utils.logger import get_logger

from .block_builder import markdown_to_blocks, parse_rich_text
from .notion_interface import INotionService

logger = get_logger(__name__)


class NotionService(INotionService):
    """
    Notion 服务类，封装了所有与 Notion API 相关的操作。
    """

    def __init__(self, token: str, default_db_id: str):
        if not token:
            raise ValueError("❌ Notion Token 不能为空")

        # 保存 token，供 requests 使用
        self.token = token
        # SDK 仅用于创建/更新页面操作 (这些操作 SDK 封装得比较好)
        self.notion = Client(auth=token)
        self.default_db_id = default_db_id

    def _append_children_in_batches(self, parent_id: str, children: List[Dict]):
        """
        🔥 递归追加 Block
        """
        if not children:
            return

        batch_size = 100
        for i in range(0, len(children), batch_size):
            batch = children[i : i + batch_size]
            sub_children_map = {}
            clean_batch = []

            for idx, block in enumerate(batch):
                block_copy = block.copy()
                b_type = block_copy.get("type")

                if b_type and "children" in block_copy.get(b_type, {}):
                    sub_children_map[idx] = block_copy[b_type].pop("children")
                elif "children" in block_copy:
                    sub_children_map[idx] = block_copy.pop("children")

                clean_batch.append(block_copy)

            try:
                # logger.info(f"📡 追加 {len(clean_batch)} 个 Block...")
                response = self.notion.blocks.children.append(
                    block_id=parent_id, children=clean_batch
                )
                results = response.get("results", [])

                for batch_idx, sub_blocks in sub_children_map.items():
                    new_parent_id = results[batch_idx]["id"]
                    self._append_children_in_batches(new_parent_id, sub_blocks)

            except Exception as e:
                logger.error(f"❌ 追加 Block 失败: {e}")
                raise e

    def fetch_database_content(self, db_id: Optional[str] = None) -> List[Dict]:
        """
        使用 requests 直接调用 API (回归原始稳定逻辑)
        """
        target_db = db_id if db_id else self.default_db_id
        if not target_db:
            logger.error("❌ 未提供 Database ID")
            return []

        clean_db_id = target_db.replace("-", "")

        # ✅ 核心修复：使用依赖注入的 Token，而不是 os.getenv
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

                # 🚀 回归 requests，稳！
                response = requests.post(url, headers=headers, json=payload)

                if response.status_code != 200:
                    logger.error(
                        f"❌ Notion API 报错 (Status {response.status_code}): {response.text}"
                    )
                    # 遇到 API 错误直接停止，防止死循环
                    break

                data = response.json()
                results = data.get("results", [])

                # 分页处理
                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor")

                for page in results:
                    page_id = page["id"]
                    properties = page.get("properties", {})

                    # 提取标题
                    title = "Untitled"
                    for prop in properties.values():
                        if isinstance(prop, dict) and prop.get("type") == "title":
                            title_objs = prop.get("title", [])
                            if title_objs:
                                title = title_objs[0].get("plain_text", "Untitled")
                            break

                    # 提取内容
                    content = self.get_page_text(page_id)
                    if content.strip():
                        pages_data.append(
                            {"id": page_id, "title": title, "content": content}
                        )
                        logger.info(f"   - ✅ 抓取成功: {title}")

            return pages_data

        except Exception as e:
            logger.error(f"❌ 数据库拉取通讯失败: {e}")
            raise e

    def create_page(
        self, title: str, children: List[Dict], icon: str = "📄", db_id: str = None
    ) -> Dict:
        """增强版创建接口：带回滚机制"""
        target_db = db_id if db_id else self.default_db_id
        if not target_db:
            raise ValueError("❌ 未配置有效的 Database ID")

        logger.info(f"✍️ [Notion] 创建页面: {title}")
        page_id = None

        try:
            # 1. 创建空页面
            response = self.notion.pages.create(
                parent={"database_id": target_db},
                icon={"type": "emoji", "emoji": icon},
                properties={"Name": {"title": [{"text": {"content": title}}]}},
                children=[],
            )
            page_id = response["id"]

            # 2. 追加内容
            if children:
                try:
                    self._append_children_in_batches(page_id, children)
                except Exception as inner_e:
                    logger.error("⚠️ 内容追加失败，执行回滚...")
                    self.delete_page(page_id)
                    raise inner_e

            return response

        except Exception as e:
            logger.error(f"❌ 页面任务失败: {e}")
            raise e

    def delete_page(self, page_id: str) -> bool:
        """归档页面"""
        try:
            self.notion.pages.update(page_id=page_id, archived=True)
            return True
        except Exception as e:
            logger.error(f"❌ 删除页面失败: {e}")
            return False

    def get_page_text(self, page_id: str) -> str:
        """提取页面文本内容"""
        try:
            # 这里的 list 方法通常 SDK 兼容性较好，保留 SDK 调用
            # 如果这里也报错，我们再改回 requests
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
        """清空并覆盖页面"""
        logger.info(f"♻️ 重写页面: {page_id}")
        try:
            # 1. 列出所有 Block
            all_block_ids = []
            has_more = True
            start_cursor = None
            while has_more:
                # 为了保持一致，这里如果是简单的 list 也可以保留 SDK
                # 如果报错再换
                res = self.notion.blocks.children.list(
                    block_id=page_id, start_cursor=start_cursor
                )
                all_block_ids.extend([b["id"] for b in res.get("results", [])])
                has_more = res.get("has_more")
                start_cursor = res.get("next_cursor")

            # 2. 并发删除
            if all_block_ids:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    executor.map(self._delete_block_worker, all_block_ids)

            # 3. 构造并写入新内容
            new_children = []
            if summary:
                new_children.append(
                    {
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "rich_text": parse_rich_text(summary),
                            "icon": {"emoji": "💡"},
                            "color": "gray_background",
                        },
                    }
                )
            new_children.extend(markdown_to_blocks(markdown_body))
            self._append_children_in_batches(page_id, new_children)
            return True
        except Exception as e:
            logger.error(f"❌ 覆盖失败: {e}")
            return False
