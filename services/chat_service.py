"""
services/chat_service.py
聊天业务服务层
"""
import json
from typing import AsyncGenerator

from langchain_core.messages import HumanMessage

from agent.agent_graph import graph
from notion.notion_ops import NotionService
from utils.logger import get_logger

logger = get_logger(__name__)


class ChatService:
    def __init__(self, config, notion_service: NotionService, llm_factory, cache=None):
        self.config = config
        self.notion_service = notion_service
        self.llm_factory = llm_factory
        self.cache = cache

    async def stream_response(
        self, query: str, thread_id: str, model_name: str, context: str = ""
    ) -> AsyncGenerator[str, None]:
        # 1. System Prompt
        source_hint = "【Current Uploaded File】" if context else ""
        system_instruction = """
        You are Exocortex, an AI assistant.
        If you use the audio tool, you MUST output the tag exactly: [AUDIO_URL: filename.mp3]
        """
        final_query = f"{system_instruction}\n\n{source_hint}:\n{context}\n\n【User Query】:\n{query}"
        model_instance = self.llm_factory(model=model_name)
        run_config = {
            "configurable": {
                "thread_id": thread_id,
                "model": model_instance,
                "notion_service": self.notion_service,
                "db_ids": {
                    "Tech": self.config.DB_TECH_ID,
                    "Spanish": self.config.DB_SPANISH_ID,
                    "General": self.config.DB_TECH_ID,
                },
            }
        }
        inputs = {"messages": [HumanMessage(content=final_query)]}
        retrieved_metadata = None

        try:
            async for event in graph.astream_events(
                inputs, config=run_config, version="v1"
            ):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield content
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    if event.get("error"):
                        logger.error(f"❌ Tool {tool_name} failed: {event['error']}")
                        continue
                    if "search" in tool_name.lower():
                        raw_output = event["data"].get("output")
                        if hasattr(raw_output, "content"):
                            raw_output = raw_output.content
                        output_dict = {}
                        if isinstance(raw_output, str):
                            try:
                                output_dict = json.loads(raw_output)
                            except json.JSONDecodeError:
                                pass
                        elif isinstance(raw_output, dict):
                            output_dict = raw_output

                        if output_dict.get("found") or output_dict.get("match"):
                            score_val = output_dict.get("score") or output_dict.get(
                                "distance", 0.0
                            )
                            retrieved_metadata = {
                                "page_id": str(output_dict.get("page_id", "")),
                                "title": output_dict.get("title", "Untitled"),
                                "matched_snippet": output_dict.get(
                                    "existing_content", ""
                                )[:200],
                                "score": float(score_val),
                            }
                            logger.info(
                                f"📡 Metadata Captured: {retrieved_metadata['title']}"
                            )
        except Exception as e:
            logger.error(f"Graph execution error: {e}", exc_info=True)
            yield f"\n[SYSTEM_ERROR: {str(e)}]"
            return

        if retrieved_metadata:
            clean_id = retrieved_metadata["page_id"].replace("-", "")
            meta = {
                "page_id": clean_id,
                "title": retrieved_metadata["title"],
                "url": f"https://www.notion.so/{clean_id}",
                "score": retrieved_metadata["score"],
                "matched_snippet": retrieved_metadata["matched_snippet"],
            }
            logger.info(f"📤 Sending Meta Tag: {clean_id}")
            yield f"\n[KNOWLEDGE_META: {json.dumps(meta, ensure_ascii=False)}]"

    # 🔥 兼容测试方法
    async def process_message(self, query: str, thread_id: str):
        model = self.llm_factory()
        run_config = {"configurable": {"model": model}}
        try:
            return await graph.ainvoke(
                {"messages": [HumanMessage(content=query)]}, config=run_config
            )
        except Exception as e:
            raise e
