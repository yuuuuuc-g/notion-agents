"""
agent/conversational_search_agent.py
对话式搜索 Agent - 支持主题澄清的智能搜索
版本：v2 (Fix Await Error) - 修复同步方法调用错误
"""
import time
from typing import Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from utils.logger import get_logger
from vector.hybrid_search import calculate_diversity, cluster_by_topic

logger = get_logger(__name__)


# =============================================================================
# 状态定义
# =============================================================================


class ConversationalSearchState(TypedDict):
    """对话式检索状态"""

    # 输入
    query: str  # 用户查询
    session_id: Optional[str]  # 会话ID
    user_choice: Optional[str]  # 用户选择 (如 "2", "数据分析")

    # 中间状态
    search_results: List[Dict]  # 搜索结果
    topics_detected: List[Dict]  # 检测到的主题
    diversity_score: float  # 多样性分数 (0-1)
    needs_clarification: bool  # 是否需要澄清
    clarification_question: str  # 澄清问题

    # 输出
    final_results: List[Dict]  # 最终结果
    response_type: Literal["results", "clarification", "error"]  # 响应类型
    metadata: Dict  # 元数据


# =============================================================================
# 节点函数
# =============================================================================


async def search_node(state: ConversationalSearchState) -> ConversationalSearchState:
    """
    搜索节点 - 执行混合检索
    """
    from core.container import container

    query = state["query"]
    logger.info(f"🔍 [ConversationalSearch] Starting search for: '{query}'")

    try:
        # 获取混合检索引擎
        vector_store = container.vector_store()

        # 执行搜索 (多取一些结果用于主题分析)
        if hasattr(vector_store, "search_with_context"):
            # 🔥 修复：search_with_context 是同步方法，不能加 await
            # 虽然 vector_store 内部使用了异步的 search_engine (在旧版本)，
            # 但 vector_store.py 中暴露的 search_with_context 封装了 loop.run_until_complete 或者本身就是同步的。
            # 根据 Turn 31 的最终代码，它是 def search_with_context(...) -> 同步方法。
            search_resp = vector_store.search_with_context(
                query=query,
                top_k=20,  # 取更多结果以便分析
            )
            # search_with_context 返回的是字典，包含 match 和 results
            results = search_resp.get("results", [])
        else:
            # 降级到普通搜索 (也是同步方法)
            search_result = vector_store.search_memory(query_text=query, n_results=20)
            results = []
            if search_result.get("match"):
                # 兼容旧接口，构造列表
                results = [search_result]

        logger.info(f"✅ [ConversationalSearch] Found {len(results)} results")

        return {
            **state,
            "search_results": results,
            "metadata": {
                "total_found": len(results),
                "search_type": "hybrid",
                "timestamp": time.time(),
            },
        }

    except Exception as e:
        logger.error(f"❌ [ConversationalSearch] Search failed: {e}")
        return {
            **state,
            "search_results": [],
            "response_type": "error",
            "metadata": {"error": str(e)},
        }


def analyze_topics_node(state: ConversationalSearchState) -> ConversationalSearchState:
    """
    主题分析节点 - 分析搜索结果的主题分布
    """
    results = state["search_results"]

    if not results:
        logger.warning("⚠️ [ConversationalSearch] No results to analyze")
        return {**state, "topics_detected": [], "diversity_score": 0.0}

    logger.info(f"📊 [ConversationalSearch] Analyzing {len(results)} results for topics")

    try:
        # 1. 主题聚类 (使用已有的工具函数)
        topics = cluster_by_topic(results, top_n_topics=5)

        # 2. 计算多样性
        diversity = calculate_diversity(results)

        # 3. 构建主题信息
        topics_info = []
        for topic_name, topic_results in topics.items():
            # 获取示例标题 (最多2个)
            sample_titles = [r.get("title", "Untitled") for r in topic_results[:2]]

            topics_info.append(
                {
                    "name": topic_name,
                    "count": len(topic_results),
                    "sample_titles": sample_titles,
                    "results": topic_results,
                    "avg_score": sum(r.get("score", 0) for r in topic_results)
                    / len(topic_results)
                    if topic_results
                    else 0,
                }
            )

        # 4. 按结果数量排序
        topics_info.sort(key=lambda t: t["count"], reverse=True)

        logger.info(
            f"✅ [ConversationalSearch] Detected {len(topics_info)} topics "
            f"(diversity: {diversity:.2f})"
        )

        return {**state, "topics_detected": topics_info, "diversity_score": diversity}

    except Exception as e:
        logger.error(f"❌ [ConversationalSearch] Topic analysis failed: {e}")
        return {**state, "topics_detected": [], "diversity_score": 0.0}


def needs_clarification_node(state: ConversationalSearchState) -> str:
    """
    判断节点 - 决定是否需要澄清
    路由决策: "ask_user" | "filter_results" | "return_results"
    """
    # 1. 如果用户已经做了选择，直接过滤
    if state.get("user_choice"):
        logger.info("🔀 [ConversationalSearch] User choice provided → filter_results")
        return "filter_results"

    # 2. 判断是否需要澄清
    topics = state.get("topics_detected", [])
    diversity = state.get("diversity_score", 0.0)
    results = state.get("search_results", [])

    # 规则 1: 没有结果 → 直接返回
    if not results:
        logger.info("🔀 [ConversationalSearch] No results → return_results")
        return "return_results"

    # 规则 2: 主题数量 >= 3
    if len(topics) >= 3:
        logger.info(
            f"🔀 [ConversationalSearch] {len(topics)} topics detected → ask_user"
        )
        return "ask_user"

    # 规则 3: 多样性 >= 0.6 (60%的结果来自不同页面/主题)
    if diversity >= 0.6:
        logger.info(
            f"🔀 [ConversationalSearch] High diversity ({diversity:.2f}) → ask_user"
        )
        return "ask_user"

    # 规则 4: 单个主题占比 < 50%
    if topics:
        max_topic_count = max(t["count"] for t in topics)
        max_topic_ratio = max_topic_count / len(results)

        if max_topic_ratio < 0.5:
            logger.info(
                f"🔀 [ConversationalSearch] No dominant topic "
                f"(max: {max_topic_ratio:.2f}) → ask_user"
            )
            return "ask_user"

    # 否则直接返回结果
    logger.info("🔀 [ConversationalSearch] Single dominant topic → return_results")
    return "return_results"


async def ask_user_node(state: ConversationalSearchState) -> ConversationalSearchState:
    """
    询问节点 - 生成澄清问题
    """
    topics = state["topics_detected"]
    query = state["query"]

    logger.info(
        f"💬 [ConversationalSearch] Generating clarification question for '{query}'"
    )

    # 构建澄清问题
    question_parts = [f"我在知识库中找到了关于 '{query}' 的多个主题：\n"]

    for idx, topic in enumerate(topics[:5], 1):
        # 示例标题
        sample_titles = "、".join(topic["sample_titles"])

        question_parts.append(
            f"{idx}. **{topic['name']}** ({topic['count']}篇)\n"
            f"   示例: {sample_titles}"
        )

    question_parts.append("\n你想了解哪个方面？请输入数字或关键词。")

    clarification_question = "\n".join(question_parts)

    return {
        **state,
        "clarification_question": clarification_question,
        "needs_clarification": True,
        "response_type": "clarification",
    }


def filter_results_node(state: ConversationalSearchState) -> ConversationalSearchState:
    """
    过滤节点 - 根据用户选择过滤结果
    """
    user_choice = state.get("user_choice", "")
    topics = state.get("topics_detected", [])

    logger.info(f"🔍 [ConversationalSearch] Filtering by user choice: '{user_choice}'")

    # 1. 解析用户选择
    selected_topic = None

    if user_choice.isdigit():
        # 数字选择
        idx = int(user_choice) - 1
        if 0 <= idx < len(topics):
            selected_topic = topics[idx]
            logger.info(
                f"✅ [ConversationalSearch] Selected topic by index: {selected_topic['name']}"
            )

    if not selected_topic:
        # 关键词匹配 (模糊匹配)
        user_choice_lower = user_choice.lower()
        for topic in topics:
            if user_choice_lower in topic["name"].lower():
                selected_topic = topic
                logger.info(
                    f"✅ [ConversationalSearch] Selected topic by keyword: {topic['name']}"
                )
                break

    # 2. 获取结果
    if selected_topic:
        final_results = selected_topic["results"][:5]
        selected_name = selected_topic["name"]
    else:
        # 没有匹配，返回所有结果
        logger.warning(
            f"⚠️ [ConversationalSearch] No match for '{user_choice}', returning all results"
        )
        final_results = state.get("search_results", [])[:5]
        selected_name = None

    return {
        **state,
        "final_results": final_results,
        "response_type": "results",
        "metadata": {
            **state.get("metadata", {}),
            "selected_topic": selected_name,
            "filtered_count": len(final_results),
            "user_choice": user_choice,
        },
    }


def return_results_node(state: ConversationalSearchState) -> ConversationalSearchState:
    """
    直接返回节点 - 直接返回搜索结果（无需澄清）
    """
    results = state.get("search_results", [])

    logger.info(
        f"📦 [ConversationalSearch] Returning {len(results[:5])} results directly"
    )

    return {
        **state,
        "final_results": results[:5],
        "response_type": "results",
        "metadata": {**state.get("metadata", {}), "clarification_needed": False},
    }


# =============================================================================
# LangGraph 工作流构建
# =============================================================================


def create_conversational_search_graph() -> StateGraph:
    """创建并编译对话式搜索工作流"""
    logger.info("🔧 [ConversationalSearch] Building workflow graph...")

    # 1. 创建图
    workflow = StateGraph(ConversationalSearchState)

    # 2. 添加节点
    workflow.add_node("search", search_node)
    workflow.add_node("analyze_topics", analyze_topics_node)
    workflow.add_node("ask_user", ask_user_node)
    workflow.add_node("filter_results", filter_results_node)
    workflow.add_node("return_results", return_results_node)

    # 3. 设置入口
    workflow.set_entry_point("search")

    # 4. 添加边
    workflow.add_edge("search", "analyze_topics")

    # 5. 添加条件边 (Router)
    workflow.add_conditional_edges(
        "analyze_topics",
        needs_clarification_node,
        {
            "ask_user": "ask_user",
            "filter_results": "filter_results",
            "return_results": "return_results",
        },
    )

    # 6. 添加结束边
    workflow.add_edge("ask_user", END)
    workflow.add_edge("filter_results", END)
    workflow.add_edge("return_results", END)

    return workflow.compile()


# 全局实例
conversational_search_graph = create_conversational_search_graph()
