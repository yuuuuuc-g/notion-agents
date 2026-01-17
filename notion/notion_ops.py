"""
notion/notion_ops.py
[Infrastructure Decoupling Refactored]
Notion 服务的具体实现类，支持依赖注入。
"""

import concurrent.futures
from typing import Dict, List, Optional

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
        # 确保是从 notion_client 导入的 Client
        self.notion = Client(auth=token)
        self.default_db_id = default_db_id

    def _append_children_in_batches(self, page_id: str, children: List[Dict]):
        """分批追加 Block，防止超过 100 个限制"""
        if not children:
            return
        batch_size = 100
        batches = [
            children[i : i + batch_size] for i in range(0, len(children), batch_size)
        ]
        logger.info(f"📡 正在分 {len(batches)} 批次上传 {len(children)} 个 Block...")
        for idx, batch in enumerate(batches):
            try:
                self.notion.blocks.children.append(block_id=page_id, children=batch)
                logger.info(f"   - ✅ 批次 {idx + 1}/{len(batches)} 上传成功。")
            except Exception as e:
                logger.error(f"   - ❌ 批次 {idx + 1} 失败: {e}")
                raise e

    def fetch_database_content(self, db_id: Optional[str] = None) -> List[Dict]:
        import os  # 确保导入 os

        import requests

        target_db = db_id if db_id else self.default_db_id
        clean_db_id = target_db.replace("-", "")

        # 核心修正：直接从环境变量获取 Token，不再去 self.notion 里面猜属性名
        token = os.getenv("NOTION_TOKEN")

        if not token:
            logger.error("❌ 未能获取到 NOTION_TOKEN，请检查 .env 文件")
            raise Exception("Missing NOTION_TOKEN")

        logger.info(f"🔍 [Standard Sync] 正在拉取数据库内容: {clean_db_id}")

        url = f"https://api.notion.com/v1/databases/{clean_db_id}/query"
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

        pages_data = []

        try:
            # 使用 requests 发起请求
            response = requests.post(url, headers=headers, json={})

            if response.status_code != 200:
                logger.error(
                    f"❌ Notion API 报错 (Status {response.status_code}): {response.text}"
                )
                return []

            results = response.json().get("results", [])

            for page in results:
                page_id = page["id"]
                properties = page.get("properties", {})

                # 寻找标题属性
                title = "Untitled"
                for prop_name, prop in properties.items():
                    if isinstance(prop, dict) and prop.get("type") == "title":
                        title_objs = prop.get("title", [])
                        if title_objs:
                            title = title_objs[0].get("plain_text", "Untitled")
                        break

                # 获取正文文本
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
        self, title: str, children: List[Dict], icon: str = "🧠", db_id: str = None
    ) -> Dict:
        """
        Exocortex 专用接口：采用“先创建、后追加”策略。
        """
        target_db = db_id if db_id else self.default_db_id
        if not target_db:
            raise ValueError("❌ 未配置有效的 Database ID！")

        logger.info(f"✍️ [Notion Service] 正在创建页面: {title}")

        try:
            # 1. 先创建一个空页面
            response = self.notion.pages.create(
                parent={"database_id": target_db},
                icon={"type": "emoji", "emoji": icon},
                properties={"Name": {"title": [{"text": {"content": title}}]}},
                children=[],
            )
            page_id = response["id"]
            logger.info(f"✅ 空页面创建成功: {page_id}")

            # 2. 批量追加内容
            if children:
                self._append_children_in_batches(page_id, children)

            return response

        except Exception as e:
            logger.error(f"❌ 页面创建失败: {e}")
            raise e

    def delete_page(self, page_id: str) -> bool:
        """归档（删除）指定页面"""
        logger.info(f"🧨 [Notion Service] 正在归档页面: {page_id}")
        try:
            self.notion.pages.update(page_id=page_id, archived=True)
            return True
        except Exception as e:
            logger.error(f"❌ 删除页面失败: {e}")
            return False

    def get_page_text(self, page_id: str) -> str:
        """提取页面文本内容"""
        logger.info(f"📖 [Notion Service] 正在读取页面: {page_id}")
        try:
            # 考虑分页处理内容，此处为简化版，拉取首屏内容
            response = self.notion.blocks.children.list(block_id=page_id)
            blocks = response.get("results", [])
            lines = []
            for b in blocks:
                b_type = b.get("type")
                # 提取富文本内容
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
            logger.error(f"❌ 读取失败: {e}")
            return ""

    def _delete_block_worker(self, block_id: str):
        """线程池辅助函数"""
        try:
            self.notion.blocks.delete(block_id=block_id)
        except Exception as e:
            logger.warning(f"   ⚠️ 删除 Block {block_id} 失败: {e}")

    def overwrite_page_content(
        self, page_id: str, markdown_body: str, summary: str = None
    ) -> bool:
        """清空并覆盖页面内容"""
        logger.info(f"♻️ [Notion Service] 正在重写页面内容: {page_id}...")
        try:
            # 1. 获取并并发删除所有 Block
            all_block_ids = []
            has_more, start_cursor = True, None
            while has_more:
                res = self.notion.blocks.children.list(
                    block_id=page_id, start_cursor=start_cursor
                )
                all_block_ids.extend([b["id"] for b in res.get("results", [])])
                has_more, start_cursor = res.get("has_more"), res.get("next_cursor")

            if all_block_ids:
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    executor.map(self._delete_block_worker, all_block_ids)

            # 2. 构造新内容
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

            # 3. 写入新内容
            self._append_children_in_batches(page_id, new_children)
            return True
        except Exception as e:
            logger.error(f"❌ 覆盖内容失败: {e}")
            return False


def create_notion_page(title: str, children: List[Dict], icon: str = "🧠"):
    """
    临时兼容函数：在 server.py 还没完全改好 Depends 之前使用。
    """
    from config.settings import SETTINGS

    service = NotionService(
        SETTINGS.NOTION_TOKEN, SETTINGS.DB_TECH_ID or SETTINGS.DB_SPANISH_ID
    )
    return service.create_page(title, children, icon)
