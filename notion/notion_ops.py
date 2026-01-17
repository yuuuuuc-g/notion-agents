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

    def _append_children_in_batches(self, parent_id: str, children: List[Dict]):
        """
        🔥 递归追加 Block：解决 Notion API 不允许在单次请求中创建深层嵌套的问题。
        逻辑：
        1. 剥离当前层级 Block 的 children。
        2. 提交当前层级的“扁平”Block。
        3. 拿到 API 返回的 ID 后，递归为有子项的 Block 追加内容。
        """
        if not children:
            return

        batch_size = 100
        # 对当前层级的 Block 进行分批处理
        for i in range(0, len(children), batch_size):
            batch = children[i : i + batch_size]

            # 🔍 1. 递归准备：剥离并记录哪些 Block 带有子项
            # 注意：我们必须深度拷贝一份，或者在 pop 后能找回关联关系
            sub_children_map = {}  # 记录 {批次内的索引: 子 Block 列表}

            clean_batch = []
            for idx, block in enumerate(batch):
                # 复制一份，避免修改原始数据影响其他逻辑
                block_copy = {k: v for k, v in block.items()}
                b_type = block_copy.get("type")

                # 如果这个 Block 内部带有嵌套内容
                if b_type and "children" in block_copy.get(b_type, {}):
                    # 剥离出子项，存入 map
                    sub_children_map[idx] = block_copy[b_type].pop("children")

                # 某些旧版逻辑可能直接在 block 根部带 children
                elif "children" in block_copy:
                    sub_children_map[idx] = block_copy.pop("children")

                clean_batch.append(block_copy)

            # 🚀 2. 提交当前这批扁平化的 Block
            try:
                logger.info(f"📡 正在向 {parent_id[:8]} 追加 {len(clean_batch)} 个基础 Block...")
                response = self.notion.blocks.children.append(
                    block_id=parent_id, children=clean_batch
                )

                # 拿到 API 返回的实际结果（包含新生成的 Block ID）
                results = response.get("results", [])

                # 🔄 3. 递归处理：如果这一批里有被剥离的子项，现在逐一挂载
                for batch_idx, sub_blocks in sub_children_map.items():
                    new_parent_id = results[batch_idx]["id"]
                    # 递归调用自身，将子项挂载到刚生成的父 Block ID 下
                    self._append_children_in_batches(new_parent_id, sub_blocks)

            except Exception as e:
                logger.error(f"❌ 追加 Block 失败: {e}")
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
        🚀 增强版创建接口：实现“事务回滚”机制。
        如果追加内容失败，自动归档（删除）已创建的空页面，保证数据一致性。
        """
        target_db = db_id if db_id else self.default_db_id
        if not target_db:
            raise ValueError("❌ 未配置有效的 Database ID！")

        logger.info(f"✍️ [Notion Service] 正在创建页面: {title}")

        page_id = None  # 追踪已创建的页面 ID 用于回滚

        try:
            # 1. 尝试创建空页面
            response = self.notion.pages.create(
                parent={"database_id": target_db},
                icon={"type": "emoji", "emoji": icon},
                properties={"Name": {"title": [{"text": {"content": title}}]}},
                children=[],
            )
            page_id = response["id"]
            logger.info(f"✅ 空页面创建成功: {page_id}")

            # 2. 递归追加内容（这里会调用我们刚才改好的递归 _append_children_in_batches）
            if children:
                try:
                    self._append_children_in_batches(page_id, children)
                    logger.info(f"🎉 页面内容同步完成: {title}")
                except Exception as inner_e:
                    # 💥 核心回滚点：内容追加失败，销毁现场
                    logger.error("⚠️ 内容追加中断，启动自动回滚逻辑...")
                    self.delete_page(page_id)
                    logger.warning(f"🧹 已清理不完整的残余页面: {page_id}")
                    raise inner_e

            return response

        except Exception as e:
            # 如果连空页面都没建成功，或者回滚后重新抛出异常
            logger.error(f"❌ [Transaction Failed] 页面任务最终失败: {e}")
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
