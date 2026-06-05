"""
Tests for OMDb Tool.

Verifies search_by_title behavior: input validation, success parsing,
not-found handling, timeout, and HTTP error scenarios.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.models import OMDbResult
from app.omdb_tool import OMDbTool


@pytest.fixture
def tool():
    """Create an OMDbTool instance with a test API key."""
    return OMDbTool(api_key="test_key", timeout=10.0)


# ──────────────────────────────────────────────
# Input validation tests
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_title_returns_error(tool):
    """Empty string title returns error without making HTTP call."""
    result = await tool.search_by_title("")
    assert result.success is False
    assert result.error == "A non-empty title is required."


@pytest.mark.asyncio
async def test_whitespace_only_title_returns_error(tool):
    """Whitespace-only title returns error without making HTTP call."""
    result = await tool.search_by_title("   \t\n  ")
    assert result.success is False
    assert result.error == "A non-empty title is required."


# ──────────────────────────────────────────────
# Successful response tests
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_successful_movie_lookup(tool):
    """Successful movie lookup extracts all metadata."""
    mock_response_data = {
        "Response": "True",
        "Title": "Inception",
        "Year": "2010",
        "Plot": "A thief who steals corporate secrets...",
        "Genre": "Action, Adventure, Sci-Fi",
        "Ratings": [{"Source": "Internet Movie Database", "Value": "8.8/10"}],
        "Type": "movie",
    }

    mock_request = httpx.Request("GET", "http://www.omdbapi.com/")
    mock_response = httpx.Response(200, json=mock_response_data, request=mock_request)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await tool.search_by_title("Inception")

    assert result.success is True
    assert result.title == "Inception"
    assert result.year == "2010"
    assert result.plot == "A thief who steals corporate secrets..."
    assert result.genre == "Action, Adventure, Sci-Fi"
    assert result.ratings == [{"Source": "Internet Movie Database", "Value": "8.8/10"}]
    assert result.content_type == "movie"
    assert result.total_seasons is None


@pytest.mark.asyncio
async def test_successful_series_lookup(tool):
    """Successful series lookup extracts totalSeasons."""
    mock_response_data = {
        "Response": "True",
        "Title": "Breaking Bad",
        "Year": "2008–2013",
        "Plot": "A chemistry teacher diagnosed with cancer...",
        "Genre": "Crime, Drama, Thriller",
        "Ratings": [{"Source": "Internet Movie Database", "Value": "9.5/10"}],
        "Type": "series",
        "totalSeasons": "5",
    }

    mock_request = httpx.Request("GET", "http://www.omdbapi.com/")
    mock_response = httpx.Response(200, json=mock_response_data, request=mock_request)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await tool.search_by_title("Breaking Bad")

    assert result.success is True
    assert result.title == "Breaking Bad"
    assert result.content_type == "series"
    assert result.total_seasons == "5"


# ──────────────────────────────────────────────
# Not found tests
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_not_found_returns_error(tool):
    """OMDb 'not found' response returns error result."""
    mock_response_data = {
        "Response": "False",
        "Error": "Movie not found!",
    }

    mock_request = httpx.Request("GET", "http://www.omdbapi.com/")
    mock_response = httpx.Response(200, json=mock_response_data, request=mock_request)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        result = await tool.search_by_title("xyznonexistent123")

    assert result.success is False
    assert "Movie not found!" in result.error


# ──────────────────────────────────────────────
# Error handling tests
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_timeout_returns_error(tool):
    """Timeout returns error result."""
    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("Connection timed out"),
    ):
        result = await tool.search_by_title("Inception")

    assert result.success is False
    assert "timed out" in result.error


@pytest.mark.asyncio
async def test_http_error_returns_error(tool):
    """HTTP error returns error result with status code."""
    mock_response = httpx.Response(500)
    mock_response.request = httpx.Request("GET", "http://www.omdbapi.com/")

    with patch(
        "httpx.AsyncClient.get",
        new_callable=AsyncMock,
        side_effect=httpx.HTTPStatusError(
            "Server Error", request=mock_response.request, response=mock_response
        ),
    ):
        result = await tool.search_by_title("Inception")

    assert result.success is False
    assert "500" in result.error
