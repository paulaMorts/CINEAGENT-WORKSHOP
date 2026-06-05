"""
Unit tests for the BedrockClient class.

Tests core logic like history management, text extraction, and tool dispatch
using mocks for the Bedrock API and OMDb tool.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bedrock_client import BedrockClient, MAX_HISTORY_MESSAGES, SYSTEM_PROMPT
from app.models import OMDbResult


@pytest.fixture
def mock_omdb_tool():
    """Create a mock OMDb tool."""
    tool = MagicMock()
    tool.search_by_title = AsyncMock(
        return_value=OMDbResult(
            success=True,
            title="The Matrix",
            year="1999",
            plot="A hacker discovers reality is a simulation.",
            genre="Action, Sci-Fi",
            ratings=[{"Source": "Internet Movie Database", "Value": "8.7/10"}],
            content_type="movie",
            total_seasons=None,
        )
    )
    return tool


@pytest.fixture
def bedrock_client(mock_omdb_tool):
    """Create a BedrockClient with a mocked boto3 client."""
    with patch("app.bedrock_client.boto3.client") as mock_boto3:
        client = BedrockClient(
            region="us-east-1",
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            omdb_tool=mock_omdb_tool,
        )
        return client


class TestBedrockClientInit:
    """Tests for BedrockClient initialization."""

    def test_init_creates_sessions_dict(self, bedrock_client):
        assert bedrock_client.sessions == {}

    def test_init_stores_region_and_model(self, bedrock_client):
        assert bedrock_client.region == "us-east-1"
        assert bedrock_client.model_id == "anthropic.claude-3-haiku-20240307-v1:0"


class TestExtractText:
    """Tests for _extract_text helper."""

    def test_extracts_single_text_block(self, bedrock_client):
        message = {"content": [{"text": "Hello, world!"}]}
        assert bedrock_client._extract_text(message) == "Hello, world!"

    def test_extracts_multiple_text_blocks(self, bedrock_client):
        message = {"content": [{"text": "Part 1"}, {"text": "Part 2"}]}
        assert bedrock_client._extract_text(message) == "Part 1\nPart 2"

    def test_skips_non_text_blocks(self, bedrock_client):
        message = {
            "content": [
                {"text": "Hello"},
                {"toolUse": {"name": "search_movie", "input": {}}},
            ]
        }
        assert bedrock_client._extract_text(message) == "Hello"

    def test_returns_empty_string_for_no_text(self, bedrock_client):
        message = {"content": [{"toolUse": {"name": "search_movie", "input": {}}}]}
        assert bedrock_client._extract_text(message) == ""


class TestTrimHistory:
    """Tests for _trim_history helper."""

    def test_does_not_trim_under_limit(self, bedrock_client):
        session_id = "test-session"
        bedrock_client.sessions[session_id] = [
            {"role": "user", "content": [{"text": f"msg {i}"}]}
            for i in range(10)
        ]
        bedrock_client._trim_history(session_id)
        assert len(bedrock_client.sessions[session_id]) == 10

    def test_trims_to_max_limit(self, bedrock_client):
        session_id = "test-session"
        bedrock_client.sessions[session_id] = [
            {"role": "user", "content": [{"text": f"msg {i}"}]}
            for i in range(25)
        ]
        bedrock_client._trim_history(session_id)
        assert len(bedrock_client.sessions[session_id]) == MAX_HISTORY_MESSAGES

    def test_keeps_most_recent_messages(self, bedrock_client):
        session_id = "test-session"
        messages = [
            {"role": "user", "content": [{"text": f"msg {i}"}]}
            for i in range(25)
        ]
        bedrock_client.sessions[session_id] = messages
        bedrock_client._trim_history(session_id)
        # Should keep messages 5 through 24 (the last 20)
        assert bedrock_client.sessions[session_id][0]["content"][0]["text"] == "msg 5"
        assert bedrock_client.sessions[session_id][-1]["content"][0]["text"] == "msg 24"


class TestProcessMessage:
    """Tests for the process_message method."""

    @pytest.mark.asyncio
    async def test_end_of_turn_returns_text(self, bedrock_client):
        """Test that end_turn stop reason extracts and returns text."""
        bedrock_client.client.converse = MagicMock(
            return_value={
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": "The Matrix is a great movie!"}],
                    }
                },
            }
        )

        result = await bedrock_client.process_message("Tell me about The Matrix", "s1")
        assert result == "The Matrix is a great movie!"

    @pytest.mark.asyncio
    async def test_tool_use_calls_omdb_tool(self, bedrock_client, mock_omdb_tool):
        """Test that tool_use stop reason dispatches to OMDb tool."""
        # First call returns tool_use, second call returns end_turn
        bedrock_client.client.converse = MagicMock(
            side_effect=[
                {
                    "stopReason": "tool_use",
                    "output": {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {
                                    "toolUse": {
                                        "toolUseId": "tool-123",
                                        "name": "search_movie",
                                        "input": {"title": "The Matrix"},
                                    }
                                }
                            ],
                        }
                    },
                },
                {
                    "stopReason": "end_turn",
                    "output": {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"text": "The Matrix (1999) is a sci-fi action film."}
                            ],
                        }
                    },
                },
            ]
        )

        result = await bedrock_client.process_message("Search The Matrix", "s1")
        assert result == "The Matrix (1999) is a sci-fi action film."
        mock_omdb_tool.search_by_title.assert_called_once_with("The Matrix")

    @pytest.mark.asyncio
    async def test_stores_messages_in_session(self, bedrock_client):
        """Test that user and assistant messages are stored in history."""
        bedrock_client.client.converse = MagicMock(
            return_value={
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": "I can help with movies!"}],
                    }
                },
            }
        )

        await bedrock_client.process_message("Hello", "session-1")

        history = bedrock_client.sessions["session-1"]
        # Should have user message + assistant message
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"][0]["text"] == "Hello"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_system_prompt_sent_to_bedrock(self, bedrock_client):
        """Test that the system prompt is always included in Converse calls."""
        bedrock_client.client.converse = MagicMock(
            return_value={
                "stopReason": "end_turn",
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"text": "Hi!"}],
                    }
                },
            }
        )

        await bedrock_client.process_message("Hi", "s1")

        call_kwargs = bedrock_client.client.converse.call_args
        system_arg = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
        assert system_arg == [{"text": SYSTEM_PROMPT}]
