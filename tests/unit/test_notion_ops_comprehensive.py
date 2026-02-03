"""
tests/unit/test_notion_ops_comprehensive.py
Notion Operations 完整测试套件 - 提升覆盖率到 85%+

目标覆盖的未测试区域：
- _append_children_in_batches 嵌套处理
- create_page 回滚逻辑
- overwrite_page_content 并发删除
- fetch_database_content 分页
- 外科手术方法（get_page_structure, update_block_text, insert_blocks_after）
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from notion.notion_ops import NotionService


# ===================================================================
# Fixtures
# ===================================================================
@pytest.fixture
def mock_notion_client():
    """Mock Notion Client"""
    return MagicMock()


@pytest.fixture
def service(mock_notion_client):
    """NotionService 实例"""
    with patch("notion.notion_ops.Client", return_value=mock_notion_client):
        return NotionService(token="test-token", default_db_id="db-123")


# ===================================================================
# 测试 _append_children_in_batches（嵌套子块）
# ===================================================================
def test_append_children_empty(service, mock_notion_client):
    """测试空 children"""
    service._append_children_in_batches("parent-id", [])
    # 不应该调用 API
    mock_notion_client.blocks.children.append.assert_not_called()


def test_append_children_simple(service, mock_notion_client):
    """测试简单 blocks（无嵌套）"""
    children = [
        {"type": "paragraph", "paragraph": {"rich_text": []}},
        {"type": "heading_1", "heading_1": {"rich_text": []}},
    ]

    mock_notion_client.blocks.children.append.return_value = {
        "results": [{"id": "block-1"}, {"id": "block-2"}]
    }

    service._append_children_in_batches("parent", children)

    # 应该调用一次 append
    assert mock_notion_client.blocks.children.append.call_count == 1


def test_append_children_with_nested(service, mock_notion_client):
    """测试嵌套 children（递归）"""
    children = [
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [],
                "children": [  # 嵌套子块
                    {"type": "paragraph", "paragraph": {"rich_text": []}}
                ],
            },
        }
    ]

    mock_notion_client.blocks.children.append.return_value = {
        "results": [{"id": "block-parent"}]
    }

    service._append_children_in_batches("parent", children)

    # 应该调用两次：父块 + 子块
    assert mock_notion_client.blocks.children.append.call_count == 2


def test_append_children_table_special_handling(service, mock_notion_client):
    """测试 table 的特殊处理（children 不应该被提取）"""
    children = [
        {
            "type": "table",
            "table": {
                "table_width": 2,
                "children": [  # table_row，不应该被提取
                    {"type": "table_row", "table_row": {"cells": []}}
                ],
            },
        }
    ]

    mock_notion_client.blocks.children.append.return_value = {
        "results": [{"id": "table-1"}]
    }

    service._append_children_in_batches("parent", children)

    # table.children 应该保留，只调用一次
    call_args = mock_notion_client.blocks.children.append.call_args
    sent_blocks = call_args[1]["children"]

    # table 的 children 应该还在
    assert "children" in sent_blocks[0]["table"]


def test_append_children_batch_size_split(service, mock_notion_client):
    """测试超过 batch_size 的分批处理"""
    # 创建 60 个 blocks（超过 batch_size=50）
    children = [
        {"type": "paragraph", "paragraph": {"rich_text": []}} for _ in range(60)
    ]

    mock_notion_client.blocks.children.append.return_value = {
        "results": [{"id": f"b-{i}"} for i in range(50)]
    }

    service._append_children_in_batches("parent", children)

    # 应该调用两次（50 + 10）
    assert mock_notion_client.blocks.children.append.call_count == 2


def test_append_children_api_error(service, mock_notion_client):
    """测试 API 错误"""
    children = [{"type": "paragraph", "paragraph": {"rich_text": []}}]

    mock_notion_client.blocks.children.append.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
        service._append_children_in_batches("parent", children)


# ===================================================================
# 测试 create_page 回滚逻辑
# ===================================================================
def test_create_page_success(service, mock_notion_client):
    """测试成功创建"""
    mock_notion_client.pages.create.return_value = {"id": "page-new"}
    mock_notion_client.blocks.children.append.return_value = {"results": []}

    result = service.create_page("Title", [{"type": "paragraph", "paragraph": {}}])

    assert result["id"] == "page-new"


def test_create_page_with_category_and_tags(service, mock_notion_client):
    """测试带 category 和 tags 创建"""
    mock_notion_client.pages.create.return_value = {"id": "page-tagged"}
    mock_notion_client.blocks.children.append.return_value = {"results": []}

    result = service.create_page(
        title="Test", children=[], category="Spanish", tags=["tag1", "tag2"]
    )

    # 【修复 1】验证返回值 (使用了 result 变量)
    # 确保服务层正确透传了 Notion API 返回的 ID
    assert result["id"] == "page-tagged"

    # 验证 properties 包含 Type 和 Tags
    call_args = mock_notion_client.pages.create.call_args
    properties = call_args[1]["properties"]

    assert "Type" in properties
    assert properties["Type"]["select"]["name"] == "Spanish"
    assert "Tags" in properties
    assert len(properties["Tags"]["multi_select"]) == 2


def test_create_page_rollback_on_content_failure(service, mock_notion_client):
    """测试内容追加失败时的回滚"""
    mock_notion_client.pages.create.return_value = {"id": "page-rollback"}

    # 模拟内容追加失败
    mock_notion_client.blocks.children.append.side_effect = Exception("Content Error")

    with pytest.raises(Exception, match="Content Error"):
        service.create_page("Title", [{"type": "paragraph", "paragraph": {}}])

    # 应该调用 delete_page 回滚
    mock_notion_client.pages.update.assert_called_once_with(
        page_id="page-rollback", archived=True
    )


def test_create_page_no_db_id(service):
    """测试缺少 database_id"""
    service.default_db_id = None

    with pytest.raises(ValueError, match="未配置有效的 Database ID"):
        service.create_page("Title", [])


# ===================================================================
# 测试 fetch_database_content 分页
# ===================================================================
def test_fetch_database_pagination(service):
    """测试分页获取"""
    # Mock requests.post 返回多页数据
    with patch("notion.notion_ops.requests.post") as mock_post:
        # 第一页
        response_1 = Mock()
        response_1.status_code = 200
        response_1.json.return_value = {
            "results": [
                {
                    "id": "p1",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "Page 1"}]}
                    },
                }
            ],
            "has_more": True,
            "next_cursor": "cursor-2",
        }

        # 第二页
        response_2 = Mock()
        response_2.status_code = 200
        response_2.json.return_value = {
            "results": [
                {
                    "id": "p2",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "Page 2"}]}
                    },
                }
            ],
            "has_more": False,
        }

        mock_post.side_effect = [response_1, response_2]

        # Mock get_page_text
        with patch.object(service, "get_page_text", return_value="Content"):
            results = service.fetch_database_content()

        # 应该获取两页
        assert len(results) == 2
        assert results[0]["title"] == "Page 1"
        assert results[1]["title"] == "Page 2"

        # 验证第二次请求带了 cursor
        second_call_payload = mock_post.call_args_list[1][1]["json"]
        assert second_call_payload["start_cursor"] == "cursor-2"


def test_fetch_database_api_error(service):
    """测试 API 错误"""
    with patch("notion.notion_ops.requests.post") as mock_post:
        response = Mock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_post.return_value = response

        results = service.fetch_database_content()

        # 应该返回空列表（不崩溃）
        assert results == []


def test_fetch_database_skip_empty_content(service):
    """测试跳过空内容页面"""
    with patch("notion.notion_ops.requests.post") as mock_post:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "results": [
                {
                    "id": "p1",
                    "properties": {
                        "Name": {"type": "title", "title": [{"plain_text": "Page"}]}
                    },
                }
            ],
            "has_more": False,
        }
        mock_post.return_value = response

        # Mock get_page_text 返回空内容
        with patch.object(service, "get_page_text", return_value="   "):
            results = service.fetch_database_content()

        # 空内容应该被跳过
        assert len(results) == 0


# ===================================================================
# 测试 overwrite_page_content 并发删除
# ===================================================================
def test_overwrite_page_content_success(service, mock_notion_client):
    """测试覆盖成功"""
    # Mock 列出 blocks
    mock_notion_client.blocks.children.list.return_value = {
        "results": [{"id": "old-block-1"}, {"id": "old-block-2"}],
        "has_more": False,
    }

    # Mock 追加新内容
    mock_notion_client.blocks.children.append.return_value = {"results": []}

    success = service.overwrite_page_content("page-123", "# New Content")

    assert success is True

    # 验证删除了旧 blocks
    assert mock_notion_client.blocks.delete.call_count == 2


def test_overwrite_page_content_with_pagination(service, mock_notion_client):
    """测试分页列出 blocks"""
    # 第一页
    call_1 = {"results": [{"id": "b1"}], "has_more": True, "next_cursor": "cursor-2"}

    # 第二页
    call_2 = {"results": [{"id": "b2"}], "has_more": False}

    mock_notion_client.blocks.children.list.side_effect = [call_1, call_2]
    mock_notion_client.blocks.children.append.return_value = {"results": []}

    success = service.overwrite_page_content("page", "Content")

    assert success is True
    # 应该列出两次
    assert mock_notion_client.blocks.children.list.call_count == 2


def test_overwrite_page_content_concurrent_delete(service, mock_notion_client):
    """测试并发删除（ThreadPoolExecutor）"""
    # 创建多个 blocks
    blocks = [{"id": f"block-{i}"} for i in range(10)]

    mock_notion_client.blocks.children.list.return_value = {
        "results": blocks,
        "has_more": False,
    }
    mock_notion_client.blocks.children.append.return_value = {"results": []}

    with patch("concurrent.futures.ThreadPoolExecutor") as mock_executor:
        mock_pool = mock_executor.return_value.__enter__.return_value

        service.overwrite_page_content("page", "New")

        # 验证使用了线程池
        mock_pool.map.assert_called_once()


def test_overwrite_page_content_error(service, mock_notion_client):
    """测试覆盖失败"""
    mock_notion_client.blocks.children.list.side_effect = Exception("List Error")

    success = service.overwrite_page_content("page", "Content")

    assert success is False


# ===================================================================
# 测试外科手术方法
# ===================================================================
def test_get_page_structure(service, mock_notion_client):
    """测试获取页面结构"""
    mock_notion_client.blocks.children.list.return_value = {
        "results": [
            {
                "id": "b1",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Text content"}]},
            },
            {
                "id": "b2",
                "type": "heading_1",
                "heading_1": {"rich_text": [{"plain_text": "Title"}]},
            },
        ],
        "has_more": False,
        "next_cursor": None,  # <--- 【关键修复】必须添加这个字段
    }

    structure = service.get_page_structure("page-123")

    assert len(structure) == 2
    assert structure[0]["block_id"] == "b1"
    assert structure[0]["type"] == "paragraph"
    assert "Text content" in structure[0]["content_preview"]


def test_get_page_structure_skip_empty_blocks(service, mock_notion_client):
    """测试跳过空 blocks"""
    mock_notion_client.blocks.children.list.return_value = {
        "results": [
            {"id": "b1", "type": "paragraph", "paragraph": {"rich_text": []}},  # 空内容
            {
                "id": "b2",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"plain_text": "Content"}]},
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }

    structure = service.get_page_structure("page")

    # 只应该返回有内容的
    assert len(structure) == 1
    assert structure[0]["block_id"] == "b2"


def test_update_block_text_success(service, mock_notion_client):
    """测试更新 block 文本"""
    success = service.update_block_text("block-123", "New text")

    assert success is True
    mock_notion_client.blocks.update.assert_called_once_with(
        block_id="block-123",
        paragraph={"rich_text": [{"text": {"content": "New text"}}]},
    )


def test_update_block_text_error(service, mock_notion_client):
    """测试更新失败"""
    mock_notion_client.blocks.update.side_effect = Exception("Update Error")

    success = service.update_block_text("block", "Text")

    assert success is False


def test_insert_blocks_after_success(service, mock_notion_client):
    """测试插入 blocks"""
    mock_notion_client.blocks.children.append.return_value = {"results": []}

    success = service.insert_blocks_after("parent", "after-block", "# New Content")

    assert success is True
    # 验证调用了 append
    mock_notion_client.blocks.children.append.assert_called_once()


def test_insert_blocks_after_error(service, mock_notion_client):
    """测试插入失败"""
    mock_notion_client.blocks.children.append.side_effect = Exception("Insert Error")

    success = service.insert_blocks_after("parent", "after", "Content")

    assert success is False


# ===================================================================
# 测试 get_page_text
# ===================================================================
def test_get_page_text_with_code(service, mock_notion_client):
    """测试提取代码块文本"""
    mock_notion_client.blocks.children.list.return_value = {
        "results": [
            {"type": "code", "code": {"rich_text": [{"plain_text": "print('hello')"}]}}
        ]
    }

    text = service.get_page_text("page-123")

    # assert "```" in text
    assert "print('hello')" in text


def test_get_page_text_error(service, mock_notion_client):
    """测试读取失败"""
    mock_notion_client.blocks.children.list.side_effect = Exception("Read Error")

    text = service.get_page_text("page")

    # 应该返回空字符串（不崩溃）
    assert text == ""


# ===================================================================
# 测试 delete_page
# ===================================================================
def test_delete_page_success(service, mock_notion_client):
    """测试删除成功"""
    success = service.delete_page("page-123")

    assert success is True
    mock_notion_client.pages.update.assert_called_once_with(
        page_id="page-123", archived=True
    )


def test_delete_page_error(service, mock_notion_client):
    """测试删除失败"""
    mock_notion_client.pages.update.side_effect = Exception("Delete Error")

    success = service.delete_page("page")

    assert success is False


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=notion.notion_ops", "--cov-report=term-missing"]
    )
