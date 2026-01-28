"""
tools/conversational_search_tool.py
对话式搜索工具 - 支持主题澄清的智能搜索

使用场景:
1. 首次搜索: conversational_search("Python")
2. 用户选择主题后: conversational_search("Python", session_id="xxx", user_choice="2")

Week 6-7 实现
"""
import json
from typing import Optional

from langchain_core.tools import tool

from agent.conversational_search_agent import (
    ConversationalSearchState,
    conversational_search_graph,
)
from services.search_session_manager import get_search_session_manager
from utils.logger import get_logger

logger = get_logger(__name__)


@tool
async def conversational_search(
    query: str, session_id: Optional[str] = None, user_choice: Optional[str] = None
) -> str:
    """
    对话式搜索工具 - 支持主题澄清的智能搜索

    当用户查询包含多个主题时，系统会询问用户想了解哪个方面，然后返回精准结果。

    使用场景:
    1. 首次搜索: 只传 query
       例: conversational_search("Python")
       可能返回: 澄清问题 (发现了基础语法、数据分析、Web开发等主题)

    2. 用户选择主题后: 传 query, session_id, user_choice
       例: conversational_search("Python", session_id="xxx", user_choice="2")
       返回: 数据分析相关的精准结果

    Args:
        query: 搜索查询词
        session_id: 会话ID (可选，用于继续上次的搜索)
        user_choice: 用户选择 (可选，可以是数字 "1", "2" 或关键词 "数据分析")

    Returns:
        JSON 字符串 (Agent 可解析)
    """
    try:
        logger.info(
            f"🔍 [ConversationalSearchTool] Query: '{query}' "
            f"(session: {session_id}, choice: {user_choice})"
        )

        # 获取会话管理器
        session_manager = get_search_session_manager()

        # 1. 检查是否是继续会话
        if session_id and user_choice:
            # 恢复会话
            session_data = await session_manager.get_session(session_id)

            if not session_data:
                logger.warning(
                    f"⚠️ [ConversationalSearchTool] Session expired: {session_id}"
                )
                return json.dumps(
                    {"type": "error", "error": "会话已过期，请重新搜索"}, ensure_ascii=False
                )

            # 构建初始状态 (直接跳到过滤节点)
            initial_state: ConversationalSearchState = {
                "query": session_data["query"],
                "session_id": session_id,
                "user_choice": user_choice,
                "search_results": session_data["search_results"],
                "topics_detected": session_data["topics_detected"],
                "diversity_score": 0.0,  # 不需要重新计算
                "needs_clarification": False,
                "clarification_question": "",
                "final_results": [],
                "response_type": "results",
                "metadata": {},
            }

            # 直接执行过滤
            # 注意: 这里我们需要手动调用 filter_results_node 的逻辑
            from agent.conversational_search_agent import filter_results_node

            result = filter_results_node(initial_state)

            # 清理会话
            await session_manager.delete_session(session_id)

            logger.info(
                f"✅ [ConversationalSearchTool] Filtered results: {len(result['final_results'])} items"
            )

        else:
            # 新搜索
            initial_state: ConversationalSearchState = {
                "query": query,
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

            result = await conversational_search_graph.ainvoke(initial_state)

            logger.info(
                f"✅ [ConversationalSearchTool] Search completed: type={result['response_type']}"
            )

        # 2. 处理结果并返回给 Agent
        if result["response_type"] == "clarification":
            # 需要澄清 - 创建会话
            new_session_id = await session_manager.create_session(
                query=result.get("query", query),
                search_results=result["search_results"],
                topics=result["topics_detected"],
            )

            response = {
                "type": "clarification",
                "question": result["clarification_question"],
                "session_id": new_session_id,
                "topics": [
                    {
                        "index": idx + 1,
                        "name": t["name"],
                        "count": t["count"],
                        "sample_titles": t["sample_titles"],
                    }
                    for idx, t in enumerate(result["topics_detected"])
                ],
            }

            logger.info(
                f"💬 [ConversationalSearchTool] Clarification needed (session: {new_session_id})"
            )

        elif result["response_type"] == "results":
            # 直接返回结果
            response = {
                "type": "results",
                "results": [
                    {
                        "title": r.get("title", "Untitled"),
                        "content": r.get("content", "")[:200] + "...",  # 截断内容
                        "page_id": r.get("page_id", ""),
                        "score": round(r.get("score", 0), 2),
                        "domain": r.get("domain", "General"),
                    }
                    for r in result["final_results"]
                ],
                "metadata": result.get("metadata", {}),
            }

            logger.info(
                f"📦 [ConversationalSearchTool] Returned {len(response['results'])} results"
            )

        elif result["response_type"] == "error":
            # 错误
            response = {
                "type": "error",
                "error": result.get("metadata", {}).get("error", "Unknown error"),
            }

            logger.error(f"❌ [ConversationalSearchTool] Error: {response['error']}")

        else:
            response = {
                "type": "error",
                "error": f"Unknown response type: {result.get('response_type')}",
            }

        return json.dumps(response, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(
            f"❌ [ConversationalSearchTool] Unexpected error: {e}", exc_info=True
        )
        return json.dumps({"type": "error", "error": str(e)}, ensure_ascii=False)
