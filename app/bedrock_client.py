"""
Bedrock Client for CineAgent.

Manages communication with Amazon Bedrock's Converse API, including
the tool-use loop for OMDb lookups. Maintains per-session conversation
history and enforces a 20-message limit.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

import boto3

from app.omdb_tool import OMDbTool

logger = logging.getLogger(__name__)

# Maximum number of messages to keep in conversation history per session
MAX_HISTORY_MESSAGES = 20

# System prompt that defines CineAgent's persona and behavior
SYSTEM_PROMPT = """You are CineAgent, a friendly and knowledgeable movie and TV series assistant.

Your capabilities:
- Search for movies and TV series using the search_movie tool
- Provide information about titles including plot, ratings, genre, and year
- Recommend similar movies or TV series based on a given title

Rules you MUST follow:
1. ONLY answer questions about movies and TV series. If a user asks about anything else (politics, cooking, sports, math, etc.), politely decline and say: "I'm CineAgent, and I can only help with movie and TV series questions. Try asking me about a film or show!"
2. When you need real data about a specific movie or TV series, use the search_movie tool. Do NOT make up movie data.
3. When recommending similar titles, FIRST use search_movie to look up the referenced title to understand its genre and themes, then suggest 3 to 5 similar titles with their release year and a brief explanation of why each is similar.
4. For TV series, ALWAYS label content as "movie" or "series" and include the number of seasons when available.
5. If a user asks about a TV series but the result shows it is a movie, inform them and offer to search for TV series alternatives.
6. If search_movie returns an error or no results, inform the user that the title was not found and ask them to verify the title name.
"""

# Tool specification for the Converse API
OMDB_TOOL_SPEC = {
    "tools": [
        {
            "toolSpec": {
                "name": "search_movie",
                "description": (
                    "Search for a movie or TV series by title using the OMDb database. "
                    "Returns metadata including title, year, plot, genre, ratings, "
                    "content type (movie or series), and number of seasons for series."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "The title of the movie or TV series to search for.",
                            }
                        },
                        "required": ["title"],
                    }
                },
            }
        }
    ]
}


class BedrockClient:
    """Communicates with Amazon Bedrock's Converse API for CineAgent.

    Handles sending user messages, processing tool-use requests (OMDb lookups),
    and maintaining per-session conversation history.

    Attributes:
        region: AWS region for the Bedrock service.
        model_id: The Bedrock model identifier to use.
        omdb_tool: The OMDb tool instance for movie searches.
        sessions: In-memory conversation history per session.
    """

    def __init__(self, region: str, model_id: str, omdb_tool: OMDbTool) -> None:
        """Initialize the Bedrock client.

        Args:
            region: AWS region where Bedrock is available (e.g. "us-east-1").
            model_id: Bedrock model ID (e.g. "anthropic.claude-3-haiku-20240307-v1:0").
            omdb_tool: An initialized OMDbTool instance for movie lookups.
        """
        self.region = region
        self.model_id = model_id
        self.omdb_tool = omdb_tool
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.sessions: Dict[str, List[Dict[str, Any]]] = {}
        self.last_posters: List[str] = []  # Poster URLs from last request

    async def process_message(self, query: str, session_id: str) -> str:
        """Process a user query and return the assistant response.

        Builds the conversation from session history, sends it to Bedrock,
        handles any tool-use requests (possibly multiple rounds), and
        returns the final text response.

        Args:
            query: The user's natural language message.
            session_id: Identifier for the conversation session.

        Returns:
            The assistant's text response.
        """
        # Reset poster URLs for this request
        self.last_posters = []

        # Get or create session history
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        history = self.sessions[session_id]

        # Add user message to history
        user_message = {"role": "user", "content": [{"text": query}]}
        history.append(user_message)

        # Build messages list from history
        messages = list(history)

        # Call Bedrock Converse API in a loop to handle multiple tool calls
        while True:
            response = await self._call_converse_async(messages)

            stop_reason = response["stopReason"]
            assistant_message = response["output"]["message"]

            # Add assistant response to messages for potential follow-up
            messages.append(assistant_message)

            if stop_reason == "tool_use":
                # Extract tool use blocks and process each one
                tool_result_content = []
                for block in assistant_message["content"]:
                    if "toolUse" in block:
                        tool_use = block["toolUse"]
                        tool_name = tool_use["name"]
                        tool_input = tool_use["input"]
                        tool_use_id = tool_use["toolUseId"]

                        # Call the OMDb tool
                        tool_result = await self._handle_tool_call(
                            tool_name, tool_input
                        )

                        tool_result_content.append(
                            {
                                "toolResult": {
                                    "toolUseId": tool_use_id,
                                    "content": [{"json": tool_result}],
                                }
                            }
                        )

                # Add tool results as a user message and continue the loop
                tool_result_message = {
                    "role": "user",
                    "content": tool_result_content,
                }
                messages.append(tool_result_message)

            elif stop_reason == "end_turn":
                # Extract text from the assistant's response
                response_text = self._extract_text(assistant_message)

                # Store assistant message in session history
                history.append(assistant_message)

                # Enforce history limit (keep most recent messages)
                self._trim_history(session_id)

                return response_text

            else:
                # Unexpected stop reason — extract whatever text is available
                response_text = self._extract_text(assistant_message)
                history.append(assistant_message)
                self._trim_history(session_id)
                return response_text

    def _call_converse(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call the Bedrock Converse API (synchronous).

        Args:
            messages: The conversation messages to send.

        Returns:
            The raw API response dictionary.
        """
        response = self.client.converse(
            modelId=self.model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig=OMDB_TOOL_SPEC,
        )
        return response

    async def _call_converse_async(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call the Bedrock Converse API without blocking the event loop.

        Runs the synchronous boto3 call in a thread executor so it doesn't
        block the async event loop (important for Chainlit).

        Args:
            messages: The conversation messages to send.

        Returns:
            The raw API response dictionary.
        """
        return await asyncio.to_thread(self._call_converse, messages)

    async def _handle_tool_call(
        self, tool_name: str, tool_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a tool call from Bedrock.

        Currently only supports the search_movie tool.

        Args:
            tool_name: Name of the tool to invoke.
            tool_input: Input parameters for the tool.

        Returns:
            A dictionary with the tool result for Bedrock.
        """
        if tool_name == "search_movie":
            title = tool_input.get("title", "")
            result = await self.omdb_tool.search_by_title(title)

            # Collect poster URL if available
            if result.success and result.poster:
                self.last_posters.append(result.poster)

            # Convert OMDbResult to a dictionary for Bedrock
            return {
                "success": result.success,
                "title": result.title,
                "year": result.year,
                "plot": result.plot,
                "genre": result.genre,
                "ratings": result.ratings,
                "content_type": result.content_type,
                "total_seasons": result.total_seasons,
                "poster": result.poster,
                "error": result.error,
            }
        else:
            logger.warning("Unknown tool requested: %s", tool_name)
            return {"error": f"Unknown tool: {tool_name}"}

    def _extract_text(self, message: Dict[str, Any]) -> str:
        """Extract text content from an assistant message.

        Args:
            message: The assistant message dictionary from Bedrock.

        Returns:
            The concatenated text content from the message.
        """
        text_parts = []
        for block in message.get("content", []):
            if "text" in block:
                text_parts.append(block["text"])
        return "\n".join(text_parts) if text_parts else ""

    def _trim_history(self, session_id: str) -> None:
        """Enforce the 20-message history limit for a session.

        Keeps only the most recent messages when the limit is exceeded.

        Args:
            session_id: The session to trim.
        """
        history = self.sessions[session_id]
        if len(history) > MAX_HISTORY_MESSAGES:
            self.sessions[session_id] = history[-MAX_HISTORY_MESSAGES:]
