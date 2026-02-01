"""
tests/tools/test_conversational_search_tool.py
针对 tools/conversational_search_tool.py 的高覆盖率测试
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 导入待测工具
from tools.conversational_search_tool import conversational_search


# === Fixtures ===
@pytest.fixture
def mock_deps():
    """Mock 核心依赖"""
    # Mock httpx.post for SiliconFlowEmbedding
    mock_httpx_response = MagicMock()
    mock_httpx_response.status_code = 200
    mock_httpx_response.json.return_value = {
        "data": [{"embedding": [0.1] * 1024, "index": 0}]
    }
    mock_httpx_response.raise_for_status = MagicMock()

    with (
        patch(
            "tools.conversational_search_tool.get_search_session_manager"
        ) as mock_get_manager,
        patch(
            "tools.conversational_search_tool.conversational_search_graph"
        ) as mock_graph,
        patch(
            "agent.conversational_search_agent.filter_results_node"
        ) as mock_filter_node,
        patch(
            "httpx.post", return_value=mock_httpx_response
        ),  # Patch httpx.post globally
    ):
        # Mock 会话管理器
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # 确保图mock有ainvoke方法
        mock_graph.ainvoke = AsyncMock()

        # 确保过滤节点有默认返回值 (改为None，避免干扰其他测试)
        mock_filter_node.return_value = None

        yield {
            "manager": mock_manager,
            "graph": mock_graph,
            "filter_node": mock_filter_node,
            "get_manager": mock_get_manager,
        }


# === 测试用例：新搜索 ===
@pytest.mark.asyncio
async def test_conversational_search_new_clarification(mock_deps):
    """测试新搜索，需要澄清的情况"""
    mock_graph = mock_deps["graph"]
    mock_manager = mock_deps["manager"]

    # 模拟图返回澄清结果
    mock_graph.ainvoke.return_value = {
        "response_type": "clarification",
        "query": "Python",
        "search_results": [{"title": "Python tutorial"}],
        "topics_detected": [
            {
                "name": "Web Development",
                "count": 5,
                "sample_titles": ["Django guide", "Flask tutorial"],
            }
        ],
        "clarification_question": "您想了解哪个主题？",
    }

    # 模拟创建会话
    mock_manager.create_session.return_value = "session_123"

    # 调用工具
    result_json = await conversational_search.ainvoke({"query": "Python"})
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "clarification"
    assert result["question"] == "您想了解哪个主题？"
    assert result["session_id"] == "session_123"
    assert len(result["topics"]) == 1
    assert result["topics"][0]["name"] == "Web Development"

    # 验证调用
    mock_graph.ainvoke.assert_called_once()
    mock_manager.create_session.assert_called_once()


@pytest.mark.asyncio
async def test_conversational_search_new_results(mock_deps):
    """测试新搜索，直接返回结果的情况"""
    mock_graph = mock_deps["graph"]

    # 模拟图返回结果
    mock_graph.ainvoke.return_value = {
        "response_type": "results",
        "final_results": [
            {
                "title": "Python基础教程",
                "content": "Python是一种编程语言...",
                "page_id": "page_1",
                "score": 0.95,
                "domain": "Programming",
            }
        ],
        "metadata": {"total": 1},
    }

    # 调用工具
    result_json = await conversational_search.ainvoke({"query": "Python基础"})
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "results"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Python基础教程"
    assert result["results"][0]["content"] == "Python是一种编程语言......"
    assert result["results"][0]["score"] == 0.95
    assert "metadata" in result

    # 验证没有创建会话
    mock_deps["manager"].create_session.assert_not_called()


@pytest.mark.asyncio
async def test_conversational_search_new_error(mock_deps):
    """测试新搜索，返回错误的情况"""
    mock_graph = mock_deps["graph"]

    # 模拟图返回错误
    mock_graph.ainvoke.return_value = {
        "response_type": "error",
        "metadata": {"error": "搜索失败"},
    }

    # 调用工具
    result_json = await conversational_search.ainvoke({"query": "Python"})
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "error"
    assert result["error"] == "搜索失败"


@pytest.mark.asyncio
async def test_conversational_search_new_unknown_response_type(mock_deps):
    """测试新搜索，未知的response_type"""
    mock_graph = mock_deps["graph"]

    # 模拟图返回未知类型
    mock_graph.ainvoke.return_value = {"response_type": "unknown", "metadata": {}}

    # 调用工具
    result_json = await conversational_search.ainvoke({"query": "Python"})
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "error"
    assert "Unknown response type" in result["error"]


# === 测试用例：继续会话 ===
@pytest.mark.asyncio
async def test_conversational_search_continue_session_success(mock_deps):
    """测试继续会话，会话存在的情况"""
    mock_manager = mock_deps["manager"]
    mock_filter_node = mock_deps["filter_node"]

    # 模拟会话数据
    session_data = {
        "query": "Python",
        "search_results": json.dumps(
            [
                {
                    "title": "Python Web",
                    "content": "Django",
                    "score": 0.9,
                    "domain": "Web",
                },
                {
                    "title": "Python Data",
                    "content": "Pandas",
                    "score": 0.8,
                    "domain": "Data",
                },
            ]
        ),
        "topics_detected": json.dumps(
            [
                {
                    "name": "Web Development",
                    "count": 3,
                    "sample_titles": ["Django"],
                    "results": [
                        {
                            "title": "Python Web",
                            "content": "Django",
                            "score": 0.9,
                            "domain": "Web",
                        }
                    ],
                },
                {
                    "name": "Data Analysis",
                    "count": 2,
                    "sample_titles": ["Pandas"],
                    "results": [
                        {
                            "title": "Python Data",
                            "content": "Pandas",
                            "score": 0.8,
                            "domain": "Data",
                        }
                    ],
                },
            ]
        ),
    }
    mock_manager.get_session.return_value = session_data

    # 模拟过滤节点返回结果
    mock_filter_node.return_value = {
        "final_results": [
            {"title": "Python Web", "content": "Django", "score": 0.9, "domain": "Web"}
        ],
        "response_type": "results",
        "metadata": {"selected_topic": "Web Development"},
    }

    # 调用工具，提供session_id和user_choice
    result_json = await conversational_search.ainvoke(
        {
            "query": "Python",  # query 参数在继续会话时可能被忽略
            "session_id": "session_123",
            "user_choice": "1",
        }
    )
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "results"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Python Web"

    # 验证调用
    mock_manager.get_session.assert_called_once_with("session_123")
    mock_filter_node.assert_called_once()
    mock_manager.delete_session.assert_called_once_with("session_123")


@pytest.mark.asyncio
async def test_conversational_search_continue_session_expired(mock_deps):
    """测试继续会话，会话过期的情况"""
    mock_manager = mock_deps["manager"]

    # 模拟会话不存在
    mock_manager.get_session.return_value = None

    # 调用工具
    result_json = await conversational_search.ainvoke(
        {"query": "Python", "session_id": "expired_session", "user_choice": "1"}
    )
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "error"
    assert result["error"] == "会话已过期，请重新搜索"

    # 验证没有调用过滤节点
    mock_deps["filter_node"].assert_not_called()


@pytest.mark.asyncio
async def test_conversational_search_continue_session_with_keyword_choice(mock_deps):
    """测试继续会话，用户选择关键词而不是数字"""
    mock_manager = mock_deps["manager"]
    mock_filter_node = mock_deps["filter_node"]

    # 模拟会话数据
    session_data = {
        "query": "Python",
        "search_results": json.dumps(
            [
                {
                    "title": "Python Web",
                    "content": "Django",
                    "score": 0.9,
                    "domain": "Web",
                }
            ]
        ),
        "topics_detected": json.dumps(
            [
                {
                    "name": "Web Development",
                    "count": 3,
                    "sample_titles": ["Django"],
                    "results": [
                        {
                            "title": "Python Web",
                            "content": "Django",
                            "score": 0.9,
                            "domain": "Web",
                        }
                    ],
                }
            ]
        ),
    }
    mock_manager.get_session.return_value = session_data

    # 模拟过滤节点返回结果
    mock_filter_node.return_value = {
        "final_results": [
            {"title": "Python Web", "content": "Django", "score": 0.9, "domain": "Web"}
        ],
        "response_type": "results",
        "metadata": {"selected_topic": "Web Development"},
    }

    # 调用工具，使用关键词选择
    result_json = await conversational_search.ainvoke(
        {
            "query": "Python",
            "session_id": "session_123",
            "user_choice": "Web Development",  # 关键词而不是数字
        }
    )
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "results"
    assert len(result["results"]) == 1

    # 验证调用
    mock_manager.get_session.assert_called_once_with("session_123")
    mock_filter_node.assert_called_once()


# === 测试用例：异常处理 ===
@pytest.mark.asyncio
async def test_conversational_search_exception_handling(mock_deps):
    """测试异常处理"""
    mock_graph = mock_deps["graph"]

    # 模拟图抛出异常
    mock_graph.ainvoke.side_effect = Exception("Something went wrong")

    # 调用工具
    result_json = await conversational_search.ainvoke({"query": "Python"})
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "error"
    assert "Something went wrong" in result["error"]


@pytest.mark.asyncio
async def test_conversational_search_continue_session_exception(mock_deps):
    """测试继续会话时的异常处理"""
    mock_manager = mock_deps["manager"]

    # 模拟会话存在但过滤节点抛出异常
    session_data = {
        "query": "Python",
        "search_results": json.dumps([]),
        "topics_detected": json.dumps([]),
    }
    mock_manager.get_session.return_value = session_data

    # 模拟过滤节点抛出异常
    mock_deps["filter_node"].side_effect = Exception("Filter error")

    # 调用工具
    result_json = await conversational_search.ainvoke(
        {"query": "Python", "session_id": "session_123", "user_choice": "1"}
    )
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "error"
    assert "Filter error" in result["error"]


# === 测试用例：边界情况 ===
@pytest.mark.asyncio
async def test_conversational_search_empty_results(mock_deps):
    """测试空结果的情况"""
    mock_graph = mock_deps["graph"]

    # 模拟图返回空结果
    mock_graph.ainvoke.return_value = {
        "response_type": "results",
        "final_results": [],
        "metadata": {},
    }

    # 调用工具
    result_json = await conversational_search.ainvoke({"query": "Nonexistent"})
    result = json.loads(result_json)

    # 验证结果
    assert result["type"] == "results"
    assert len(result["results"]) == 0


@pytest.mark.asyncio
async def test_conversational_search_result_truncation(mock_deps):
    """测试结果内容截断"""
    mock_graph = mock_deps["graph"]

    # 模拟长内容结果
    long_content = "a" * 300
    mock_graph.ainvoke.return_value = {
        "response_type": "results",
        "final_results": [
            {
                "title": "Long Content",
                "content": long_content,
                "page_id": "page_1",
                "score": 0.5,
                "domain": "Test",
            }
        ],
        "metadata": {},
    }

    # 调用工具
    result_json = await conversational_search.ainvoke({"query": "test"})
    result = json.loads(result_json)

    # 验证内容被截断
    assert result["type"] == "results"
    assert len(result["results"][0]["content"]) <= 203  # 200 + "..."
    assert result["results"][0]["content"].endswith("...")
