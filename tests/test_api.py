"""
Tests for the FastAPI /chat endpoint.

Covers valid requests, validation errors, timeouts, connection errors,
and unexpected errors.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import app, set_bedrock_client


@pytest.fixture(autouse=True)
def reset_bedrock_client():
    """Reset the bedrock_client before each test."""
    set_bedrock_client(None)
    yield
    set_bedrock_client(None)


@pytest.fixture
def mock_bedrock():
    """Provide a mock Bedrock client."""
    client = AsyncMock()
    client.process_message = AsyncMock(return_value="This is a response about movies.")
    set_bedrock_client(client)
    return client


@pytest.fixture
def client():
    """Provide a FastAPI test client."""
    return TestClient(app)


class TestChatEndpointSuccess:
    """Tests for successful /chat requests."""

    def test_valid_request_returns_200(self, client, mock_bedrock):
        """Valid request returns 200 with response and session_id."""
        response = client.post(
            "/chat",
            json={"query": "Tell me about Inception", "session_id": "session-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["response"] == "This is a response about movies."
        assert data["session_id"] == "session-123"

    def test_bedrock_called_with_correct_args(self, client, mock_bedrock):
        """Bedrock client is called with the query and session_id."""
        client.post(
            "/chat",
            json={"query": "What is The Matrix?", "session_id": "abc"},
        )
        mock_bedrock.process_message.assert_called_once_with("What is The Matrix?", "abc")


class TestChatEndpointValidation:
    """Tests for request validation (HTTP 422)."""

    def test_missing_query_returns_422(self, client, mock_bedrock):
        """Missing query field returns 422."""
        response = client.post("/chat", json={"session_id": "abc"})
        assert response.status_code == 422

    def test_empty_query_returns_422(self, client, mock_bedrock):
        """Empty query returns 422."""
        response = client.post("/chat", json={"query": "", "session_id": "abc"})
        assert response.status_code == 422

    def test_query_too_long_returns_422(self, client, mock_bedrock):
        """Query exceeding 2000 chars returns 422."""
        long_query = "a" * 2001
        response = client.post(
            "/chat", json={"query": long_query, "session_id": "abc"}
        )
        assert response.status_code == 422

    def test_missing_session_id_returns_422(self, client, mock_bedrock):
        """Missing session_id returns 422."""
        response = client.post("/chat", json={"query": "Hello"})
        assert response.status_code == 422

    def test_empty_session_id_returns_422(self, client, mock_bedrock):
        """Empty session_id returns 422."""
        response = client.post("/chat", json={"query": "Hello", "session_id": ""})
        assert response.status_code == 422


class TestChatEndpointTimeout:
    """Tests for timeout handling (HTTP 503)."""

    def test_timeout_returns_503(self, client, mock_bedrock):
        """30-second timeout returns 503 with safe message."""
        mock_bedrock.process_message = AsyncMock(side_effect=asyncio.TimeoutError())
        response = client.post(
            "/chat",
            json={"query": "Tell me about movies", "session_id": "s1"},
        )
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "AI service temporarily unavailable"
        # Ensure no internal details exposed
        assert "traceback" not in str(data).lower()
        assert "file" not in str(data).lower()


class TestChatEndpointConnectionError:
    """Tests for Bedrock connection errors (HTTP 503)."""

    def test_client_error_returns_503(self, client, mock_bedrock):
        """Botocore ClientError returns 503 with safe message."""
        # Create a mock exception that looks like botocore ClientError
        error = type("ClientError", (Exception,), {})()
        mock_bedrock.process_message = AsyncMock(side_effect=error)
        response = client.post(
            "/chat",
            json={"query": "Tell me about Inception", "session_id": "s1"},
        )
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "AI service temporarily unavailable"

    def test_endpoint_connection_error_returns_503(self, client, mock_bedrock):
        """Botocore EndpointConnectionError returns 503 with safe message."""
        error = type("EndpointConnectionError", (Exception,), {})()
        mock_bedrock.process_message = AsyncMock(side_effect=error)
        response = client.post(
            "/chat",
            json={"query": "Movies?", "session_id": "s1"},
        )
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "AI service temporarily unavailable"


class TestChatEndpointUnexpectedError:
    """Tests for unexpected errors (HTTP 500)."""

    def test_unexpected_error_returns_500(self, client, mock_bedrock):
        """Unexpected exception returns 500 with generic message."""
        mock_bedrock.process_message = AsyncMock(
            side_effect=RuntimeError("something broke internally")
        )
        response = client.post(
            "/chat",
            json={"query": "Hello", "session_id": "s1"},
        )
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "An internal error occurred. Please try again later."
        # Ensure no internal details exposed
        assert "something broke" not in str(data)
        assert "RuntimeError" not in str(data)
        assert "traceback" not in str(data).lower()

    def test_no_bedrock_client_returns_500(self, client):
        """No bedrock client configured returns 500."""
        response = client.post(
            "/chat",
            json={"query": "Hello", "session_id": "s1"},
        )
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
