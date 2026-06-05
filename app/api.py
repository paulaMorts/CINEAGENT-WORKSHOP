"""
FastAPI application for CineAgent.

Exposes the POST /chat endpoint that accepts user queries and returns
AI-generated responses about movies and TV series. Handles timeouts,
connection errors, and unexpected exceptions with safe error messages.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.models import ChatRequest, ChatResponse, ErrorResponse

logger = logging.getLogger(__name__)

# FastAPI application instance
app = FastAPI(title="CineAgent API", description="Movie and TV series chat agent")

# Module-level Bedrock client dependency.
# Set externally (e.g. by main.py) before the app starts serving requests.
# Can be overridden in tests for mocking.
bedrock_client: Optional[object] = None

# Timeout in seconds for the Bedrock client call
BEDROCK_TIMEOUT_SECONDS = 30


def set_bedrock_client(client: object) -> None:
    """Set the Bedrock client dependency for the API.

    Call this at application startup to inject the initialized
    BedrockClient instance.

    Args:
        client: An initialized BedrockClient instance.
    """
    global bedrock_client
    bedrock_client = client


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message and return the agent response.

    Forwards the user's query and session ID to the Bedrock client,
    enforces a 30-second timeout, and returns the response. On error,
    returns appropriate HTTP status codes with safe messages.

    Args:
        request: The incoming chat request with query and session_id.

    Returns:
        ChatResponse with the agent's response text and session ID.
    """
    if bedrock_client is None:
        logger.error("Bedrock client is not initialized")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="An internal error occurred. Please try again later."
            ).model_dump(),
        )

    try:
        # Call Bedrock client with a 30-second timeout
        response_text = await asyncio.wait_for(
            bedrock_client.process_message(request.query, request.session_id),
            timeout=BEDROCK_TIMEOUT_SECONDS,
        )
        return ChatResponse(response=response_text, session_id=request.session_id)

    except asyncio.TimeoutError:
        # Bedrock did not respond within 30 seconds
        logger.warning(
            "Bedrock client timed out after %d seconds for session %s",
            BEDROCK_TIMEOUT_SECONDS,
            request.session_id,
        )
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error="AI service temporarily unavailable"
            ).model_dump(),
        )

    except Exception as exc:
        # Check for Bedrock connection errors (botocore exceptions)
        exc_type_name = type(exc).__name__
        if exc_type_name in ("ClientError", "EndpointConnectionError"):
            logger.error(
                "Bedrock connection error at %s: [%s]",
                datetime.now(timezone.utc).isoformat(),
                exc_type_name,
            )
            return JSONResponse(
                status_code=503,
                content=ErrorResponse(
                    error="AI service temporarily unavailable"
                ).model_dump(),
            )

        # Unexpected error — log full details, return generic message
        logger.error(
            "Unexpected error at %s: type=%s",
            datetime.now(timezone.utc).isoformat(),
            exc_type_name,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="An internal error occurred. Please try again later."
            ).model_dump(),
        )
