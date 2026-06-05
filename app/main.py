"""
CineAgent Main Entry Point.

This module is the Chainlit application entry point that also initializes
all backend components. Run with: chainlit run app/main.py

On startup it:
1. Loads configuration from environment variables
2. Initializes the OMDb tool with the API key
3. Initializes the Bedrock client with the region, model ID, and OMDb tool
4. Wires the Bedrock client into the FastAPI app for the /chat endpoint

The Chainlit handlers provide the chat UI, while the FastAPI /chat endpoint
remains available for programmatic access.
"""

import logging
import uuid
from typing import Optional

import chainlit as cl
from app.api import app as fastapi_app, set_bedrock_client
from app.bedrock_client import BedrockClient
from app.config import load_config
from app.data_layer import JSONDataLayer
from app.omdb_tool import OMDbTool

logger = logging.getLogger(__name__)

# --- Startup: load config and initialize components ---

# Load configuration from environment variables.
# If any required variable is missing, this will log an error and exit.
config = load_config()

# Initialize the OMDb tool with the API key from config
omdb_tool = OMDbTool(api_key=config.omdb_api_key)

# Initialize the Bedrock client with region, model ID, and the OMDb tool
bedrock_client = BedrockClient(
    region=config.aws_region,
    model_id=config.bedrock_model_id,
    omdb_tool=omdb_tool,
)

# Wire the Bedrock client into the FastAPI /chat endpoint
set_bedrock_client(bedrock_client)

# Initialize the data layer for conversation history persistence
@cl.data_layer
def get_data_layer():
    return JSONDataLayer()

logger.info(
    "CineAgent initialized: region=%s, model=%s",
    config.aws_region,
    config.bedrock_model_id,
)


# --- Authentication (required for conversation history) ---


@cl.header_auth_callback
async def header_auth_callback(headers: dict) -> Optional[cl.User]:
    """Auto-authenticate all users for the workshop.

    This enables conversation history without requiring login.
    Every user is treated as 'workshop-user'.
    """
    return cl.User(identifier="workshop-user", metadata={"role": "user"})


# --- Chainlit Handlers ---


@cl.on_chat_start
async def on_chat_start():
    """Initialize a new chat session.

    Generates a unique session_id and stores it in the user session
    so it can be reused across messages in the same conversation.
    """
    session_id = str(uuid.uuid4())
    cl.user_session.set("session_id", session_id)
    logger.info("New chat session started: %s", session_id)


@cl.on_message
async def on_message(message: cl.Message):
    """Handle an incoming user message.

    Sends the user query directly to the Bedrock client (not via HTTP),
    then displays the assistant response in the chat thread.
    Chainlit automatically shows a loading indicator while this async
    handler is running.

    Args:
        message: The incoming Chainlit message from the user.
    """
    session_id = cl.user_session.get("session_id")
    print(f"[CINEAGENT] session_id={session_id}, query={message.content[:50]}")

    if not session_id:
        session_id = str(uuid.uuid4())
        cl.user_session.set("session_id", session_id)
        print(f"[CINEAGENT] Created fallback session_id={session_id}")

    try:
        # Call Bedrock client directly (not via HTTP endpoint)
        response_text = await bedrock_client.process_message(
            query=message.content,
            session_id=session_id,
        )
    except Exception as exc:
        import traceback
        print(f"[CINEAGENT ERROR] {type(exc).__name__}: {exc}")
        traceback.print_exc()
        logger.error("Error processing message: %s", exc, exc_info=True)
        response_text = (
            "Sorry, I encountered an error processing your request. "
            "Please try again."
        )

    # Display poster images before the text response (if any were found)
    posters = bedrock_client.last_posters
    if posters:
        elements = []
        for i, poster_url in enumerate(posters):
            elements.append(
                cl.Image(url=poster_url, name=f"poster_{i}", display="inline")
            )
        await cl.Message(content="", elements=elements).send()

    # Send the text response back to the user in the chat thread
    await cl.Message(content=response_text).send()
