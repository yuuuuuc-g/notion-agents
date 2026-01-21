"""
Mock LLM Provider for testing.

Provides controllable LLM responses without actual API calls,
allowing deterministic testing of agent behaviors.
"""

from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, BaseMessage


class MockChatModel:
    """
    Mock ChatOpenAI-compatible model for testing.

    Features:
    - Configurable response sequences
    - Call tracking for verification
    - Streaming simulation support
    - Tool call simulation
    """

    def __init__(
        self,
        responses: Optional[List[str]] = None,
        tool_calls: Optional[List[Dict]] = None,
    ):
        """
        Initialize mock chat model.

        Args:
            responses: List of response strings to return in sequence
            tool_calls: Optional list of tool calls to simulate
        """
        self.responses = responses or ["This is a mock AI response."]
        self.tool_calls = tool_calls or []
        self.call_count = 0
        self.call_history: List[Dict] = []
        self.streaming = True  # Simulate streaming capability

    def invoke(self, input_data: Union[str, List[BaseMessage]]) -> AIMessage:
        """
        Synchronous invoke (for non-async contexts).

        Args:
            input_data: Input message or message list

        Returns:
            AIMessage with mock response
        """
        self._record_call(input_data)
        response_text = self._get_next_response()

        return AIMessage(
            content=response_text,
            tool_calls=self._get_tool_calls_for_response(),
        )

    async def ainvoke(self, input_data: Union[str, List[BaseMessage]]) -> AIMessage:
        """
        Async invoke for LangChain compatibility.

        Args:
            input_data: Input message or message list

        Returns:
            AIMessage with mock response
        """
        return self.invoke(input_data)

    async def astream(self, input_data: Union[str, List[BaseMessage]]):
        """
        Async streaming for simulating SSE responses.

        Args:
            input_data: Input message or message list

        Yields:
            AIMessage chunks
        """
        self._record_call(input_data)
        response_text = self._get_next_response()

        # Simulate streaming by yielding word by word
        words = response_text.split()
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield AIMessage(content=chunk)

    def bind_tools(self, tools: List[Any]) -> "MockChatModel":
        """
        Bind tools to the model (for tool-using agents).

        Args:
            tools: List of LangChain tools

        Returns:
            Self for chaining
        """
        self.bound_tools = tools
        return self

    def _record_call(self, input_data: Any):
        """Record call for history tracking."""
        self.call_history.append(
            {
                "input": input_data,
                "call_number": self.call_count,
            }
        )

    def _get_next_response(self) -> str:
        """Get next response from the sequence."""
        response = self.responses[self.call_count % len(self.responses)]
        self.call_count += 1
        return response

    def _get_tool_calls_for_response(self) -> List[Dict]:
        """Get tool calls for current response if any."""
        if self.tool_calls and self.call_count <= len(self.tool_calls):
            return [self.tool_calls[self.call_count - 1]]
        return []

    # --- Test Helper Methods ---

    def reset(self):
        """Reset mock state for test isolation."""
        self.call_count = 0
        self.call_history.clear()

    def set_responses(self, responses: List[str]):
        """Set new response sequence."""
        self.responses = responses
        self.call_count = 0

    def set_tool_calls(self, tool_calls: List[Dict]):
        """Set tool calls to simulate."""
        self.tool_calls = tool_calls

    def get_last_input(self) -> Optional[Any]:
        """Get the last input received."""
        if self.call_history:
            return self.call_history[-1]["input"]
        return None


class MockStreamingResponse:
    """
    Mock for simulating LangGraph streaming events.

    Use this to test agent graph streaming behavior.
    """

    def __init__(self, events: Optional[List[Dict]] = None):
        """
        Initialize with predefined events.

        Args:
            events: List of event dicts to yield
        """
        self.events = events or [
            {
                "event": "on_chat_model_stream",
                "data": {"chunk": AsyncMock(content="Mock streaming response")},
            }
        ]

    async def __aiter__(self):
        """Async iterator for streaming events."""
        for event in self.events:
            yield event


def create_mock_astream_events(responses: List[str]):
    """
    Factory function to create mock astream_events generator.

    Args:
        responses: List of response strings

    Returns:
        Async generator function for patching graph.astream_events
    """

    async def mock_astream_events(*args, **kwargs):
        for response in responses:
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": AsyncMock(content=response)},
            }

    return mock_astream_events
