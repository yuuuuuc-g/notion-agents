"""
Mock Notion Service for testing.

Implements INotionService interface with in-memory storage,
allowing tests to verify Notion operations without API calls.
"""

import uuid
from typing import Dict, List, Optional, Tuple

from notion.notion_interface import INotionService


class MockNotionService(INotionService):
    """
    Mock implementation of Notion service for testing.

    Features:
    - In-memory page storage
    - Call history tracking for verification
    - Configurable failure simulation
    """

    def __init__(self, should_fail: bool = False):
        """
        Initialize mock Notion service.

        Args:
            should_fail: If True, operations will raise exceptions
        """
        self.pages: Dict[str, Dict] = {}
        self.call_history: List[Tuple[str, ...]] = []
        self.should_fail = should_fail
        self.default_db_id = "mock-database-id"

    def create_page(
        self, title: str, children: List[Dict], icon: str = "🧠", db_id: str = None
    ) -> Dict:
        """
        Create a mock page.

        Args:
            title: Page title
            children: Block children
            icon: Page icon emoji
            db_id: Target database ID (optional)

        Returns:
            Dict containing page id

        Raises:
            Exception: If should_fail is True
        """
        if self.should_fail:
            raise Exception("Mock Notion API failure")

        page_id = f"mock-page-{uuid.uuid4().hex[:8]}"
        self.pages[page_id] = {
            "id": page_id,
            "title": title,
            "children": children,
            "icon": icon,
            "db_id": db_id or self.default_db_id,
            "archived": False,
        }
        self.call_history.append(("create_page", title, page_id))

        return {"id": page_id}

    def delete_page(self, page_id: str) -> bool:
        """
        Delete (archive) a mock page.

        Args:
            page_id: Page ID to delete

        Returns:
            True if page was deleted, False otherwise
        """
        if self.should_fail:
            raise Exception("Mock Notion API failure")

        if page_id in self.pages:
            self.pages[page_id]["archived"] = True
            self.call_history.append(("delete_page", page_id))
            return True
        return False

    def get_page_text(self, page_id: str) -> str:
        """
        Get page content as plain text.

        Args:
            page_id: Page ID to read

        Returns:
            Page content as string
        """
        if page_id in self.pages:
            page = self.pages[page_id]
            # Extract text from children blocks
            texts = []
            for block in page.get("children", []):
                block_type = block.get("type", "")
                if block_type and block_type in block:
                    rich_text = block[block_type].get("rich_text", [])
                    for rt in rich_text:
                        texts.append(rt.get("text", {}).get("content", ""))
            return "\n".join(texts)
        return ""

    def fetch_database_content(self, db_id: Optional[str] = None) -> List[Dict]:
        """
        Fetch all pages in a database.

        Args:
            db_id: Database ID (optional)

        Returns:
            List of page data dicts
        """
        target_db = db_id or self.default_db_id
        result = []
        for page_id, page in self.pages.items():
            if page.get("db_id") == target_db and not page.get("archived"):
                result.append(
                    {
                        "id": page_id,
                        "title": page["title"],
                        "content": self.get_page_text(page_id),
                    }
                )
        return result

    def overwrite_page_content(
        self, page_id: str, markdown_body: str, summary: str = None
    ) -> bool:
        """
        Overwrite page content.

        Args:
            page_id: Page ID to overwrite
            markdown_body: New content in markdown
            summary: Optional summary

        Returns:
            True if successful
        """
        if self.should_fail:
            raise Exception("Mock Notion API failure")

        if page_id in self.pages:
            # Simulate converting markdown to blocks
            self.pages[page_id]["children"] = [
                {
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": markdown_body}}]},
                }
            ]
            if summary:
                self.pages[page_id]["summary"] = summary
            self.call_history.append(("overwrite_page_content", page_id))
            return True
        return False

    # --- Test Helper Methods ---

    def reset(self):
        """Reset mock state for test isolation."""
        self.pages.clear()
        self.call_history.clear()
        self.should_fail = False

    def get_call_count(self, method_name: str) -> int:
        """Get number of calls to a specific method."""
        return sum(1 for call in self.call_history if call[0] == method_name)

    def was_called(self, method_name: str) -> bool:
        """Check if a method was called."""
        return any(call[0] == method_name for call in self.call_history)

    def get_page(self, page_id: str) -> Optional[Dict]:
        """Get page data by ID (for test assertions)."""
        return self.pages.get(page_id)
