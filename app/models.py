"""
Data models for CineAgent.

This module defines all request/response models used by the FastAPI backend
and the structured result type returned by the OMDb tool.

- ChatRequest / ChatResponse: Pydantic models for the /chat endpoint
- ErrorResponse: Pydantic model for API error responses
- OMDbResult: Dataclass representing parsed OMDb API results
"""

from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Pydantic models for the FastAPI /chat endpoint
# ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Incoming chat request from the frontend.

    Attributes:
        query: The user's natural language message (1-2000 characters).
        session_id: Identifier for the conversation session (1-128 characters).
    """

    query: str = Field(..., min_length=1, max_length=2000)
    session_id: str = Field(..., min_length=1, max_length=128)


class ChatResponse(BaseModel):
    """Response returned to the frontend.

    Attributes:
        response: The agent's natural language response text.
        session_id: The session identifier echoed back to the client.
    """

    response: str
    session_id: str


class ErrorResponse(BaseModel):
    """Error response for API errors.

    Attributes:
        error: A short, user-safe error message.
        detail: Optional additional detail about the error.
    """

    error: str
    detail: Optional[str] = None


# ──────────────────────────────────────────────
# Dataclass for OMDb API results
# ──────────────────────────────────────────────


@dataclass
class OMDbResult:
    """Structured result from an OMDb API query.

    Attributes:
        success: Whether the API call returned a valid result.
        title: The movie or series title.
        year: Release year (or year range for series).
        plot: Short plot summary.
        genre: Comma-separated genre list.
        ratings: List of rating sources and values (e.g. [{"Source": "IMDb", "Value": "8.1/10"}]).
        content_type: Either "movie" or "series".
        total_seasons: Number of seasons (only for series).
        error: Error message when success is False.
    """

    success: bool
    title: Optional[str] = None
    year: Optional[str] = None
    plot: Optional[str] = None
    genre: Optional[str] = None
    ratings: Optional[List[dict]] = None
    content_type: Optional[str] = None  # "movie" or "series"
    total_seasons: Optional[str] = None
    poster: Optional[str] = None  # URL to the movie/series poster image
    error: Optional[str] = None
