"""
Mock Vector Store for testing.

Implements IVectorStore interface with in-memory storage,
allowing tests to verify vector operations without Qdrant.
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from vector.vector_interface import IVectorStore


class MockVectorStore(IVectorStore):
    """
    Mock implementation of vector store for testing.

    Features:
    - In-memory storage with simple keyword matching
    - Call history tracking
    - Configurable search behavior
    - Domain filtering support
    """

    def __init__(self, should_fail: bool = False):
        """
        Initialize mock vector store.

        Args:
            should_fail: If True, operations will raise exceptions
        """
        self.memories: Dict[str, Dict[str, Any]] = {}
        self.call_history: List[Tuple[str, ...]] = []
        self.should_fail = should_fail
        self.search_results: Optional[Dict] = None  # Override search results

    def add_memory(
        self,
        page_id: str,
        text: str,
        *,
        title: str = None,
        domain: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        skip_if_exists: bool = False,
    ) -> bool:
        """
        Add memory to the mock store.

        Args:
            page_id: Unique page identifier
            text: Content to store
            title: Optional title
            domain: Optional domain category
            metadata: Optional additional metadata
            skip_if_exists: Skip if page already exists

        Returns:
            True if added successfully

        Raises:
            Exception: If should_fail is True
        """
        if self.should_fail:
            raise Exception("Mock Vector Store failure")

        if skip_if_exists and page_id in self.memories:
            self.call_history.append(("add_memory_skipped", page_id))
            return False

        self.memories[page_id] = {
            "text": text,
            "title": title or "Untitled",
            "domain": domain or "General",
            "metadata": metadata or {},
        }
        self.call_history.append(("add_memory", page_id, title))
        return True

    def search_memory(
        self,
        query_text: str,
        n_results: int = 3,
        domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search memories with simple keyword matching.

        Args:
            query_text: Search query
            n_results: Maximum number of results
            domain: Optional domain filter

        Returns:
            Dict with match status and results
        """
        if self.should_fail:
            raise Exception("Mock Vector Store failure")

        self.call_history.append(("search_memory", query_text, domain))

        # Allow test to override search results
        if self.search_results is not None:
            return self.search_results

        # Simple keyword matching simulation
        query_lower = query_text.lower()
        matches: List[Tuple[str, Dict, float]] = []

        for page_id, data in self.memories.items():
            # Apply domain filter
            if domain and domain != "All" and data["domain"] != domain:
                continue

            # Simple relevance scoring based on keyword presence
            text_lower = data["text"].lower()
            title_lower = data["title"].lower()

            score = 0.0
            if query_lower in text_lower:
                score += 0.7
            if query_lower in title_lower:
                score += 0.3

            # Partial matching
            query_words = query_lower.split()
            for word in query_words:
                if word in text_lower:
                    score += 0.1
                if word in title_lower:
                    score += 0.05

            if score > 0:
                matches.append((page_id, data, min(score, 1.0)))

        if not matches:
            return {"match": False}

        # Sort by score descending
        matches.sort(key=lambda x: x[2], reverse=True)
        best_match = matches[0]

        return {
            "match": True,
            "page_id": best_match[0],
            "title": best_match[1]["title"],
            "distance": best_match[2],  # Actually similarity score
            "metadata": {
                "content": best_match[1]["text"][:500],
                "matched_snippet": best_match[1]["text"][:200],
                "summary": best_match[1]["metadata"].get("summary", ""),
            },
        }

    def page_exists(self, page_id: str) -> bool:
        """
        Check if a page exists in the store.

        Args:
            page_id: Page ID to check

        Returns:
            True if page exists
        """
        return page_id in self.memories

    # --- Test Helper Methods ---

    def reset(self):
        """Reset mock state for test isolation."""
        self.memories.clear()
        self.call_history.clear()
        self.should_fail = False
        self.search_results = None

    def set_search_results(self, results: Dict):
        """Override search results for specific test scenarios."""
        self.search_results = results

    def get_call_count(self, method_name: str) -> int:
        """Get number of calls to a specific method."""
        return sum(1 for call in self.call_history if call[0] == method_name)

    def was_called(self, method_name: str) -> bool:
        """Check if a method was called."""
        return any(call[0] == method_name for call in self.call_history)

    def get_memory(self, page_id: str) -> Optional[Dict]:
        """Get stored memory by ID (for test assertions)."""
        return self.memories.get(page_id)

    def get_all_memories(self) -> Dict[str, Dict]:
        """Get all stored memories (for test assertions)."""
        return self.memories.copy()

    def add_test_data(self, data: List[Dict]):
        """
        Bulk add test data.

        Args:
            data: List of dicts with page_id, text, title, domain
        """
        for item in data:
            self.add_memory(
                page_id=item.get("page_id", str(uuid.uuid4())),
                text=item["text"],
                title=item.get("title"),
                domain=item.get("domain"),
                metadata=item.get("metadata"),
            )
