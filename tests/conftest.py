"""
Pytest configuration and fixtures for Exocortex tests.
"""

import asyncio
import os
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

# Import the FastAPI app
from server import app


def pytest_configure():
    """Configure pytest with custom settings."""
    # Set test environment
    os.environ["TESTING"] = "true"
    # Disable external API calls by default
    os.environ["USE_LOCAL_NANOGPT"] = "true"
    # Use mock API keys
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["SILICON_KEY"] = "test-key"
    os.environ["NOTION_TOKEN"] = "test-token"
    os.environ["API_SECRET"] = "test-secret"
    os.environ["NOTION_DATABASE_ID"] = "test-db-id"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client."""
    with patch("server.redis_client") as mock_redis:
        mock_redis.ping = Mock(return_value=True)
        mock_redis.exists = Mock(return_value=True)
        mock_redis.get = Mock(return_value='{"test": "data"}')
        mock_redis.set = Mock(return_value=True)
        mock_redis.delete = Mock(return_value=1)
        yield mock_redis


@pytest.fixture(scope="function")
def mock_chromadb():
    """Mock ChromaDB client and collection."""
    with (
        patch("vector.vector_store.client") as mock_client,
        patch("vector.vector_store.collection") as mock_collection,
    ):
        # Mock client
        mock_client.get_or_create_collection = Mock(return_value=mock_collection)

        # Mock collection methods
        mock_collection.add = Mock()
        mock_collection.query = Mock(
            return_value={
                "documents": [["test document"]],
                "metadatas": [[{"parent_id": "test-parent"}]],
                "distances": [[0.1]],
            }
        )
        mock_collection.count = Mock(return_value=10)

        yield mock_client, mock_collection


@pytest.fixture(scope="function")
def mock_notion():
    """Mock Notion client."""
    with patch("notion.notion_ops.notion") as mock_notion:
        mock_notion.pages.create = Mock(return_value={"id": "test-page-id"})
        mock_notion.blocks.children.append = Mock()
        mock_notion.blocks.delete = Mock()
        mock_notion.blocks.children.list = Mock(
            return_value={"results": [], "has_more": False}
        )
        yield mock_notion


@pytest.fixture(scope="function")
def mock_openai():
    """Mock OpenAI client (used by embedding provider)."""
    with patch("vector.embedding_provider.OpenAI") as mock_openai_class:
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_embedding = Mock()
        mock_embedding.data = [Mock(embedding=[0.1] * 768)]
        mock_client.embeddings.create = Mock(return_value=mock_embedding)

        yield mock_client


@pytest.fixture(scope="function")
def test_client(mock_redis, mock_chromadb, mock_notion, mock_openai):
    """FastAPI TestClient with mocked external dependencies."""
    # Override settings for testing
    from config import settings

    settings.SETTINGS.USE_LOCAL_NANOGPT = True

    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="function")
def auth_headers():
    """Generate authentication headers for API tests."""
    return {"Authorization": "Bearer test-secret"}
