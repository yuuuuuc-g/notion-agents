"""
tests/agent/test_conversational_search_agent.py
ConversationalSearchAgent 完整测试
"""

from unittest.mock import MagicMock, patch

import pytest

from agent.conversational_search_agent import (
    analyze_topics_node,
    ask_user_node,
    create_conversational_search_graph,
    filter_results_node,
    needs_clarification_node,
    return_results_node,
    search_node,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_search_results():
    """示例搜索结果"""
    return [
        {
            "title": "Python 基础语法",
            "content": "...",
            "score": 0.9,
            "page_id": "page1",
            "domain": "Tech",
        },
        {
            "title": "Python 数据分析",
            "content": "...",
            "score": 0.85,
            "page_id": "page2",
            "domain": "Tech",
        },
        {
            "title": "Python Web开发",
            "content": "...",
            "score": 0.8,
            "page_id": "page3",
            "domain": "Tech",
        },
    ]


@pytest.fixture
def sample_topics():
    """示例主题"""
    return [
        {
            "name": "基础语法",
            "count": 3,
            "sample_titles": ["Python 基础", "变量与类型"],
            "results": [{"title": "Python 基础", "score": 0.9}],
            "avg_score": 0.9,
        },
        {
            "name": "数据分析",
            "count": 2,
            "sample_titles": ["NumPy", "Pandas"],
            "results": [{"title": "NumPy", "score": 0.85}],
            "avg_score": 0.85,
        },
        {
            "name": "Web开发",
            "count": 2,
            "sample_titles": ["Flask", "Django"],
            "results": [{"title": "Flask", "score": 0.8}],
            "avg_score": 0.8,
        },
    ]


@pytest.fixture
def base_state():
    """基础状态"""
    return {
        "query": "Python",
        "session_id": None,
        "user_choice": None,
        "search_results": [],
        "topics_detected": [],
        "diversity_score": 0.0,
        "needs_clarification": False,
        "clarification_question": "",
        "final_results": [],
        "response_type": "results",
        "metadata": {},
    }


# =============================================================================
# search_node 测试
# =============================================================================


@pytest.mark.asyncio
async def test_search_node_success(base_state):
    """测试搜索节点成功"""
    mock_vector_store = MagicMock()
    mock_vector_store.search_with_context.return_value = {
        "match": True,
        "results": [{"title": "test", "score": 0.9}],
    }

    with patch("core.container.container") as mock_container:
        mock_container.vector_store.return_value = mock_vector_store

        result = await search_node(base_state)

        assert "search_results" in result
        assert len(result["search_results"]) == 1
        assert result["search_results"][0]["title"] == "test"
        assert result["metadata"]["total_found"] == 1


@pytest.mark.asyncio
async def test_search_node_fallback_to_search_memory(base_state):
    """测试降级到 search_memory"""
    mock_vector_store = MagicMock()
    # 没有 search_with_context 方法
    del mock_vector_store.search_with_context

    mock_vector_store.search_memory.return_value = {
        "match": True,
        "title": "test",
        "score": 0.9,
    }

    with patch("core.container.container") as mock_container:
        mock_container.vector_store.return_value = mock_vector_store

        result = await search_node(base_state)

        assert "search_results" in result
        assert len(result["search_results"]) == 1


@pytest.mark.asyncio
async def test_search_node_error(base_state):
    """测试搜索节点错误处理"""
    with patch("core.container.container") as mock_container:
        mock_container.vector_store.side_effect = Exception("Search error")

        result = await search_node(base_state)

        assert result["search_results"] == []
        assert result["response_type"] == "error"
        assert "error" in result["metadata"]


# =============================================================================
# analyze_topics_node 测试
# =============================================================================


def test_analyze_topics_node_success(base_state, sample_search_results):
    """测试主题分析节点成功"""
    state = {**base_state, "search_results": sample_search_results}

    with patch("agent.conversational_search_agent.cluster_by_topic") as mock_cluster:
        with patch(
            "agent.conversational_search_agent.calculate_diversity"
        ) as mock_diversity:
            mock_cluster.return_value = {
                "基础语法": [sample_search_results[0]],
                "数据分析": [sample_search_results[1]],
                "Web开发": [sample_search_results[2]],
            }
            mock_diversity.return_value = 0.7

            result = analyze_topics_node(state)

            assert len(result["topics_detected"]) == 3
            assert result["diversity_score"] == 0.7

            # 验证主题信息结构
            topic = result["topics_detected"][0]
            assert "name" in topic
            assert "count" in topic
            assert "sample_titles" in topic
            assert "results" in topic
            assert "avg_score" in topic


def test_analyze_topics_node_empty_results(base_state):
    """测试没有搜索结果"""
    result = analyze_topics_node(base_state)

    assert result["topics_detected"] == []
    assert result["diversity_score"] == 0.0


def test_analyze_topics_node_error(base_state, sample_search_results):
    """测试主题分析错误处理"""
    state = {**base_state, "search_results": sample_search_results}

    with patch(
        "agent.conversational_search_agent.cluster_by_topic",
        side_effect=Exception("Cluster error"),
    ):
        result = analyze_topics_node(state)

        assert result["topics_detected"] == []
        assert result["diversity_score"] == 0.0


def test_analyze_topics_node_sorting(base_state, sample_search_results):
    """测试主题按数量排序"""
    # 准备 9 个结果；主题列表需为 5、3、2 条以便验证排序
    five_items = [
        {"title": f"基础{i}", "score": 0.9, "page_id": f"p{i}"} for i in range(5)
    ]
    three_items = sample_search_results[:3]
    two_items = sample_search_results[:2]
    state = {**base_state, "search_results": five_items + three_items + two_items}

    with patch("agent.conversational_search_agent.cluster_by_topic") as mock_cluster:
        with patch(
            "agent.conversational_search_agent.calculate_diversity"
        ) as mock_diversity:
            mock_cluster.return_value = {
                "基础语法": five_items,  # 5个
                "数据分析": two_items,  # 2个
                "Web开发": three_items,  # 3个
            }
            mock_diversity.return_value = 0.7

            result = analyze_topics_node(state)

            # 验证按数量降序排序
            assert result["topics_detected"][0]["count"] == 5  # 基础语法
            assert result["topics_detected"][1]["count"] == 3  # Web开发
            assert result["topics_detected"][2]["count"] == 2  # 数据分析


# =============================================================================
# needs_clarification_node 测试
# =============================================================================


def test_needs_clarification_with_user_choice(base_state):
    """测试已有用户选择时直接过滤"""
    state = {**base_state, "user_choice": "1"}

    result = needs_clarification_node(state)

    assert result == "filter_results"


def test_needs_clarification_no_results(base_state):
    """测试没有结果时直接返回"""
    result = needs_clarification_node(base_state)

    assert result == "return_results"


def test_needs_clarification_many_topics(
    base_state, sample_topics, sample_search_results
):
    """测试主题数量 >= 3 时需要澄清"""
    state = {
        **base_state,
        "search_results": sample_search_results,
        "topics_detected": sample_topics,  # 3个主题
        "diversity_score": 0.5,
    }

    result = needs_clarification_node(state)

    assert result == "ask_user"


def test_needs_clarification_high_diversity(base_state, sample_search_results):
    """测试高多样性时需要澄清"""
    state = {
        **base_state,
        "search_results": sample_search_results,
        "topics_detected": [{"name": "topic1", "count": 5}],  # 只有1个主题
        "diversity_score": 0.7,  # 但多样性高
    }

    result = needs_clarification_node(state)

    assert result == "ask_user"


def test_needs_clarification_no_dominant_topic(base_state, sample_search_results):
    """测试没有主导主题时需要澄清"""
    # 创建一个均匀分布的主题列表
    topics = [
        {"name": "topic1", "count": 3},
        {"name": "topic2", "count": 3},
        {"name": "topic3", "count": 3},
    ]

    state = {
        **base_state,
        "search_results": sample_search_results * 3,  # 9个结果
        "topics_detected": topics,
        "diversity_score": 0.5,
    }

    result = needs_clarification_node(state)

    # 最大主题占比 = 3/9 = 0.33 < 0.5
    assert result == "ask_user"


def test_needs_clarification_dominant_topic(base_state, sample_search_results):
    """测试有主导主题时直接返回结果"""
    topics = [
        {"name": "dominant_topic", "count": 8},  # 主导主题
        {"name": "minor_topic", "count": 2},
    ]
    # 必须使 len(search_results)==10，这样 max_topic_ratio = 8/10 = 0.8 > 0.5
    ten_results = (sample_search_results * 4)[:10]

    state = {
        **base_state,
        "search_results": ten_results,
        "topics_detected": topics,
        "diversity_score": 0.5,
    }

    result = needs_clarification_node(state)

    # 最大主题占比 = 8/10 = 0.8 > 0.5 → 直接返回结果
    assert result == "return_results"


# =============================================================================
# ask_user_node 测试
# =============================================================================


@pytest.mark.asyncio
async def test_ask_user_node(base_state, sample_topics):
    """测试询问节点生成澄清问题"""
    state = {
        **base_state,
        "query": "Python",
        "topics_detected": sample_topics,
    }

    result = await ask_user_node(state)

    assert result["needs_clarification"] is True
    assert result["response_type"] == "clarification"
    assert "clarification_question" in result

    question = result["clarification_question"]
    assert "Python" in question
    assert "1. **基础语法**" in question
    assert "2. **数据分析**" in question
    assert "3. **Web开发**" in question


@pytest.mark.asyncio
async def test_ask_user_node_limits_topics(base_state):
    """测试只显示前5个主题"""
    # 创建10个主题
    many_topics = [
        {
            "name": f"主题{i}",
            "count": 10 - i,
            "sample_titles": [f"标题{i}-1", f"标题{i}-2"],
            "results": [],
            "avg_score": 0.9,
        }
        for i in range(10)
    ]

    state = {
        **base_state,
        "query": "test",
        "topics_detected": many_topics,
    }

    result = await ask_user_node(state)

    question = result["clarification_question"]

    # 验证只包含前5个主题
    assert "5. **主题4**" in question
    assert "6. **主题5**" not in question


# =============================================================================
# filter_results_node 测试
# =============================================================================


def test_filter_results_by_index(base_state, sample_topics):
    """测试通过数字索引过滤结果"""
    state = {
        **base_state,
        "user_choice": "2",  # 选择第2个主题
        "topics_detected": sample_topics,
    }

    result = filter_results_node(state)

    assert result["response_type"] == "results"
    assert len(result["final_results"]) > 0
    assert result["metadata"]["selected_topic"] == "数据分析"
    assert result["metadata"]["user_choice"] == "2"


def test_filter_results_by_keyword(base_state, sample_topics):
    """测试通过关键词过滤结果"""
    state = {
        **base_state,
        "user_choice": "数据分析",  # 关键词匹配
        "topics_detected": sample_topics,
    }

    result = filter_results_node(state)

    assert result["response_type"] == "results"
    assert result["metadata"]["selected_topic"] == "数据分析"


def test_filter_results_partial_keyword(base_state, sample_topics):
    """测试部分关键词匹配"""
    state = {
        **base_state,
        "user_choice": "数据",  # 部分匹配
        "topics_detected": sample_topics,
    }

    result = filter_results_node(state)

    assert result["metadata"]["selected_topic"] == "数据分析"


def test_filter_results_case_insensitive(base_state, sample_topics):
    """测试大小写不敏感"""
    state = {
        **base_state,
        "user_choice": "WEB",  # 大写
        "topics_detected": sample_topics,
    }

    result = filter_results_node(state)

    assert result["metadata"]["selected_topic"] == "Web开发"


def test_filter_results_invalid_index(base_state, sample_topics, sample_search_results):
    """测试无效索引"""
    state = {
        **base_state,
        "user_choice": "99",  # 超出范围
        "topics_detected": sample_topics,
        "search_results": sample_search_results,
    }

    result = filter_results_node(state)

    # 应该返回所有结果
    assert result["metadata"]["selected_topic"] is None
    assert len(result["final_results"]) <= 5


def test_filter_results_no_match(base_state, sample_topics, sample_search_results):
    """测试没有匹配的选择"""
    state = {
        **base_state,
        "user_choice": "不存在的主题",
        "topics_detected": sample_topics,
        "search_results": sample_search_results,
    }

    result = filter_results_node(state)

    # 应该返回所有结果
    assert result["metadata"]["selected_topic"] is None


def test_filter_results_limits_to_5(base_state, sample_topics):
    """测试限制返回5个结果"""
    # 创建有很多结果的主题
    many_results = [{"title": f"结果{i}", "score": 0.9} for i in range(10)]

    topics_with_many_results = [
        {
            "name": "大主题",
            "count": 10,
            "sample_titles": ["test1", "test2"],
            "results": many_results,
            "avg_score": 0.9,
        }
    ]

    state = {
        **base_state,
        "user_choice": "1",
        "topics_detected": topics_with_many_results,
    }

    result = filter_results_node(state)

    # 应该只返回5个
    assert len(result["final_results"]) == 5


# =============================================================================
# return_results_node 测试
# =============================================================================


def test_return_results_node(base_state, sample_search_results):
    """测试直接返回结果节点"""
    state = {
        **base_state,
        "search_results": sample_search_results,
    }

    result = return_results_node(state)

    assert result["response_type"] == "results"
    assert len(result["final_results"]) == 3
    assert result["metadata"]["clarification_needed"] is False


def test_return_results_node_limits_to_5(base_state):
    """测试限制返回5个结果"""
    many_results = [{"title": f"结果{i}", "score": 0.9} for i in range(10)]

    state = {
        **base_state,
        "search_results": many_results,
    }

    result = return_results_node(state)

    assert len(result["final_results"]) == 5


def test_return_results_node_empty(base_state):
    """测试空结果"""
    result = return_results_node(base_state)

    assert result["final_results"] == []


# =============================================================================
# create_conversational_search_graph 测试
# =============================================================================


def test_create_conversational_search_graph():
    """测试创建工作流图"""
    graph = create_conversational_search_graph()

    # 验证图已编译
    assert graph is not None


@pytest.mark.asyncio
async def test_graph_flow_no_clarification(sample_search_results):
    """测试工作流：不需要澄清"""
    mock_vector_store = MagicMock()
    mock_vector_store.search_with_context.return_value = {
        "match": True,
        "results": sample_search_results[:1],  # 只返回1个结果
    }

    with patch("core.container.container") as mock_container:
        with patch(
            "agent.conversational_search_agent.cluster_by_topic"
        ) as mock_cluster:
            with patch(
                "agent.conversational_search_agent.calculate_diversity"
            ) as mock_diversity:
                mock_container.vector_store.return_value = mock_vector_store

                # 只有1个主题，不需要澄清
                mock_cluster.return_value = {"单一主题": sample_search_results[:1]}
                mock_diversity.return_value = 0.3

                graph = create_conversational_search_graph()

                initial_state = {
                    "query": "test",
                    "session_id": None,
                    "user_choice": None,
                    "search_results": [],
                    "topics_detected": [],
                    "diversity_score": 0.0,
                    "needs_clarification": False,
                    "clarification_question": "",
                    "final_results": [],
                    "response_type": "results",
                    "metadata": {},
                }

                result = await graph.ainvoke(initial_state)

                # 应该直接返回结果
                assert result["response_type"] == "results"
                assert len(result["final_results"]) > 0


@pytest.mark.asyncio
async def test_graph_flow_with_clarification(sample_search_results):
    """测试工作流：需要澄清"""
    mock_vector_store = MagicMock()
    mock_vector_store.search_with_context.return_value = {
        "match": True,
        "results": sample_search_results,  # 多个结果
    }

    with patch("core.container.container") as mock_container:
        with patch(
            "agent.conversational_search_agent.cluster_by_topic"
        ) as mock_cluster:
            with patch(
                "agent.conversational_search_agent.calculate_diversity"
            ) as mock_diversity:
                mock_container.vector_store.return_value = mock_vector_store

                # 多个主题，需要澄清
                mock_cluster.return_value = {
                    "主题1": sample_search_results[:1],
                    "主题2": sample_search_results[1:2],
                    "主题3": sample_search_results[2:3],
                }
                mock_diversity.return_value = 0.7

                graph = create_conversational_search_graph()

                initial_state = {
                    "query": "test",
                    "session_id": None,
                    "user_choice": None,
                    "search_results": [],
                    "topics_detected": [],
                    "diversity_score": 0.0,
                    "needs_clarification": False,
                    "clarification_question": "",
                    "final_results": [],
                    "response_type": "results",
                    "metadata": {},
                }

                result = await graph.ainvoke(initial_state)

                # 应该请求澄清
                assert result["response_type"] == "clarification"
                assert result["needs_clarification"] is True
                assert len(result["clarification_question"]) > 0


@pytest.mark.asyncio
async def test_graph_flow_with_user_choice(sample_search_results):
    """测试工作流：带用户选择"""
    mock_vector_store = MagicMock()
    mock_vector_store.search_with_context.return_value = {
        "match": True,
        "results": sample_search_results,
    }

    with patch("core.container.container") as mock_container:
        with patch(
            "agent.conversational_search_agent.cluster_by_topic"
        ) as mock_cluster:
            with patch(
                "agent.conversational_search_agent.calculate_diversity"
            ) as mock_diversity:
                mock_container.vector_store.return_value = mock_vector_store

                mock_cluster.return_value = {
                    "主题1": sample_search_results[:1],
                    "主题2": sample_search_results[1:2],
                    "主题3": sample_search_results[2:3],
                }
                mock_diversity.return_value = 0.7

                graph = create_conversational_search_graph()

                # 提供用户选择
                initial_state = {
                    "query": "test",
                    "session_id": None,
                    "user_choice": "1",  # 用户选择了第1个主题
                    "search_results": [],
                    "topics_detected": [],
                    "diversity_score": 0.0,
                    "needs_clarification": False,
                    "clarification_question": "",
                    "final_results": [],
                    "response_type": "results",
                    "metadata": {},
                }

                result = await graph.ainvoke(initial_state)

                # 应该直接返回过滤后的结果
                assert result["response_type"] == "results"
                assert "selected_topic" in result["metadata"]


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=agent.conversational_search_agent",
            "--cov-report=term-missing",
        ]
    )
