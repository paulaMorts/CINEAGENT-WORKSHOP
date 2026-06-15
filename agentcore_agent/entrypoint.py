"""
CineAgent Entrypoint for AgentCore Runtime.

Uses boto3 Bedrock Converse API directly (lightweight, no heavy deps).
Connects to AgentCore Memory for session history and uses the Gateway
tool for OMDb lookups.
"""

import json
import logging
import os
import urllib.request
import urllib.error

import boto3

logger = logging.getLogger(__name__)

# System prompt
SYSTEM_PROMPT = """You are CineAgent, a friendly and knowledgeable movie and TV series assistant.

Your capabilities:
- Search for movies and TV series using the search_movie tool
- Provide information about titles including plot, ratings, genre, and year
- Recommend similar movies or TV series based on a given title

Rules you MUST follow:
1. ONLY answer questions about movies and TV series. If a user asks about anything else, politely decline and say: "I'm CineAgent, and I can only help with movie and TV series questions. Try asking me about a film or show!"
2. When you need real data about a specific movie or TV series, use the search_movie tool. Do NOT make up movie data.
3. When recommending similar titles, FIRST use search_movie to look up the referenced title to understand its genre and themes, then suggest 3 to 5 similar titles with their release year and a brief explanation of why each is similar.
4. For TV series, ALWAYS label content as "movie" or "series" and include the number of seasons when available.
5. If a user asks about a TV series but the result shows it is a movie, inform them and offer to search for TV series alternatives.
6. If search_movie returns an error or no results, inform the user that the title was not found and ask them to verify the title name.
"""

MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
MEMORY_ID = os.environ.get("MEMORY_ID", "")
OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "de3d5a9d")

# Tool spec for Bedrock Converse API
TOOL_CONFIG = {
    "tools": [{
        "toolSpec": {
            "name": "search_movie",
            "description": "Search for a movie or TV series by title using the OMDb database. Returns title, year, plot, genre, ratings, type, seasons, and poster URL.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "The title of the movie or TV series to search for."}
                    },
                    "required": ["title"]
                }
            }
        }
    }]
}

# Initialize boto3 clients
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")

# In-memory session storage (per-runtime instance)
sessions = {}
MAX_MESSAGES = 20


def search_omdb(title):
    """Call OMDb API directly via urllib (no httpx needed)."""
    url = f"http://www.omdbapi.com/?t={urllib.request.quote(title)}&apikey={OMDB_API_KEY}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("Response") == "True":
                poster = data.get("Poster", "N/A")
                if poster == "N/A":
                    poster = None
                return {
                    "success": True,
                    "title": data.get("Title"),
                    "year": data.get("Year"),
                    "plot": data.get("Plot"),
                    "genre": data.get("Genre"),
                    "ratings": data.get("Ratings"),
                    "content_type": data.get("Type"),
                    "total_seasons": data.get("totalSeasons"),
                    "poster": poster,
                }
            else:
                return {"success": False, "error": data.get("Error", "Not found")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def invoke(payload, context=None):
    """Handle an invocation from AgentCore Runtime."""
    if isinstance(payload, str):
        payload = json.loads(payload)

    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id", "default")

    # Get or create session
    if session_id not in sessions:
        sessions[session_id] = []
    history = sessions[session_id]

    # Add user message
    history.append({"role": "user", "content": [{"text": prompt}]})

    # Build messages from history
    messages = list(history)
    posters = []

    # Converse loop (handle tool use)
    while True:
        response = bedrock.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig=TOOL_CONFIG,
        )

        stop_reason = response["stopReason"]
        assistant_msg = response["output"]["message"]
        messages.append(assistant_msg)

        if stop_reason == "tool_use":
            tool_results = []
            for block in assistant_msg["content"]:
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    title = tool_use["input"].get("title", "")
                    result = search_omdb(title)

                    # Collect poster
                    if result.get("success") and result.get("poster"):
                        posters.append(result["poster"])

                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool_use["toolUseId"],
                            "content": [{"json": result}],
                        }
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Extract text
            text_parts = []
            for block in assistant_msg.get("content", []):
                if "text" in block:
                    text_parts.append(block["text"])
            response_text = "\n".join(text_parts)

            # Store in session history
            history.append(assistant_msg)

            # Trim history
            if len(history) > MAX_MESSAGES:
                sessions[session_id] = history[-MAX_MESSAGES:]

            return json.dumps({
                "response": response_text,
                "posters": posters,
            })
