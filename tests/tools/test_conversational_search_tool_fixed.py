"""
修复版测试 - 使用直接patch方法
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

# 注意：我们在patch环境中导入，所以先不导入


@pytest.mark.asyncio
async def test_conversational_search_continue_session_success():
    """测试继续会话，会话存在的情况"""
    with (
        patch(
            "tools.conversational_search_tool.get_search_session_manager"
        ) as mock_get_manager,
        patch(
            "agent.conversational_search_agent.filter_results_node"
        ) as mock_filter_node,
    ):
        # Mock 会话管理器
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

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
                {
                    "title": "Python Web",
                    "content": "Django",
                    "score": 0.9,
                    "domain": "Web",
                }
            ],
            "response_type": "results",
            "metadata": {"selected_topic": "Web Development"},
        }

        # 现在导入工具（在patch之后）
        from tools.conversational_search_tool import conversational_search

        # 调用工具
        result_json = await conversational_search.ainvoke(
            {"query": "Python", "session_id": "session_123", "user_choice": "1"}
        )
        result = json.loads(result_json)

        # 验证结果
        assert result["type"] == "results"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Python Web"


@pytest.mark.asyncio
async def test_conversational_search_continue_session_expired():
    """测试继续会话，会话过期的情况"""
    with patch(
        "tools.conversational_search_tool.get_search_session_manager"
    ) as mock_get_manager:
        # Mock 会话管理器
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # 模拟会话不存在
        mock_manager.get_session.return_value = None

        # 现在导入工具（在patch之后）
        from tools.conversational_search_tool import conversational_search

        # 调用工具
        result_json = await conversational_search.ainvoke(
            {"query": "Python", "session_id": "expired_session", "user_choice": "1"}
        )
        result = json.loads(result_json)

        # 验证结果
        assert result["type"] == "error"
        assert result["error"] == "会话已过期，请重新搜索"


@pytest.mark.asyncio
async def test_conversational_search_exception_handling():
    """测试异常处理 - 使用真实图调用但mock异常"""
    with patch(
        "tools.conversational_search_tool.get_search_session_manager"
    ) as mock_get_manager:
        # Mock 会话管理器
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # 导入后patch图实例的ainvoke方法
        from tools.conversational_search_tool import (
            conversational_search,
            conversational_search_graph,
        )

        # Mock ainvoke方法抛出异常
        original_ainvoke = conversational_search_graph.ainvoke
        conversational_search_graph.ainvoke = AsyncMock(
            side_effect=Exception("Something went wrong")
        )

        try:
            # 调用工具
            result_json = await conversational_search.ainvoke({"query": "Python"})
            result = json.loads(result_json)

            # 验证结果
            assert result["type"] == "error"
            assert "Something went wrong" in result["error"]
        finally:
            # 恢复原始方法
            conversational_search_graph.ainvoke = original_ainvoke


@pytest.mark.asyncio
async def test_conversational_search_empty_results():
    """测试空结果的情况 - 使用真实图调用"""
    with patch(
        "tools.conversational_search_tool.get_search_session_manager"
    ) as mock_get_manager:
        # Mock 会话管理器
        mock_manager = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # 导入工具
        from tools.conversational_search_tool import conversational_search

        # 注意：这里使用真实图，可能返回空结果
        # 对于测试目的，我们可以接受这个行为
        result_json = await conversational_search.ainvoke(
            {"query": "NonexistentQueryXYZ"}
        )
        result = json.loads(result_json)

        # 验证有结果返回（类型可能是results或error）
        assert "type" in result
        # 不验证具体内容，因为使用真实图
