"""
AgentCore Client for CineAgent.

Drop-in replacement for BedrockClient that invokes the CineAgent deployed
on AgentCore Runtime instead of calling the Bedrock Converse API directly.

Maintains the same interface as BedrockClient so main.py and api.py
require minimal changes:
- async process_message(query, session_id) -> str
- last_posters property -> list[str]
"""

import asyncio
import json
import logging
from typing import Any

import boto3
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
)

logger = logging.getLogger(__name__)


class AgentCoreClient:
    """Invokes the CineAgent deployed on AgentCore Runtime.

    This client sends user prompts to the remote agent and parses the
    response, extracting both the text reply and any poster URLs found
    during tool use.

    Attributes:
        runtime_arn: The ARN of the deployed AgentCore Runtime agent.
        region: AWS region where AgentCore Runtime is deployed.
        last_posters: Poster URLs from the most recent invocation.
    """

    def __init__(self, runtime_arn: str, region: str) -> None:
        """Initialize the AgentCore client.

        Args:
            runtime_arn: ARN of the deployed agent on AgentCore Runtime.
            region: AWS region for the AgentCore service (e.g. "us-east-1").
        """
        self.runtime_arn = runtime_arn
        self.region = region
        self._last_posters: list[str] = []
        self._client = boto3.client("bedrock-agentcore", region_name=region)

    @property
    def last_posters(self) -> list[str]:
        """Poster URLs from the most recent invocation."""
        return self._last_posters

    async def process_message(self, query: str, session_id: str) -> str:
        """Send a message to the deployed agent and return the text response.

        Maintains the same interface as BedrockClient.process_message so
        main.py and api.py require minimal changes.

        Args:
            query: The user's natural language message.
            session_id: Identifier for the conversation session.

        Returns:
            The assistant's text response.

        Raises:
            ConnectionError: When the AgentCore Runtime is unreachable.
            RuntimeError: When the agent returns an error.
        """
        # Reset posters for this request
        self._last_posters = []

        # Build the invocation payload
        payload = json.dumps({
            "prompt": query,
            "session_id": session_id,
        })

        # Use asyncio.to_thread to avoid blocking the event loop
        # (same pattern as BedrockClient._call_converse_async)
        try:
            response = await asyncio.to_thread(self._invoke_agent, payload)
        except EndpointConnectionError as e:
            logger.error("Cannot connect to AgentCore Runtime: %s", e)
            raise ConnectionError(
                "Unable to connect to AgentCore Runtime. Check your network and region settings."
            ) from e
        except NoCredentialsError as e:
            logger.error("AWS credentials not configured: %s", e)
            raise ConnectionError(
                "AWS credentials not configured. Check your AWS credentials."
            ) from e
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error("AgentCore Runtime error [%s]: %s", error_code, error_msg)
            raise RuntimeError(
                f"AgentCore Runtime error: {error_msg}"
            ) from e
        except Exception as e:
            logger.error("Unexpected error invoking AgentCore Runtime: %s", e)
            raise RuntimeError(
                f"Unexpected error communicating with AgentCore Runtime: {e}"
            ) from e

        # Parse the response
        return self._parse_response(response)

    def _invoke_agent(self, payload: str) -> dict[str, Any]:
        """Invoke the agent on AgentCore Runtime (synchronous).

        Args:
            payload: JSON-encoded invocation payload.

        Returns:
            The parsed response dictionary from the agent.
        """
        response = self._client.invoke_agent_runtime(
            agentRuntimeArn=self.runtime_arn,
            payload=payload,
            contentType='application/json',
            accept='application/json',
        )

        # Read the response body (streaming response)
        response_body = response.get("body", b"")
        if hasattr(response_body, "read"):
            response_body = response_body.read()
        if isinstance(response_body, bytes):
            response_body = response_body.decode("utf-8")

        return json.loads(response_body)

    def _parse_response(self, response: dict[str, Any]) -> str:
        """Parse the agent response to extract text and poster URLs.

        Args:
            response: The parsed JSON response from the agent.
                Expected format: {"response": str, "posters": list[str]}

        Returns:
            The assistant's text response.

        Raises:
            RuntimeError: If the response format is unexpected.
        """
        # Extract text response
        response_text = response.get("response", "")
        if not response_text:
            logger.warning("Agent returned empty response: %s", response)
            response_text = "I'm sorry, I couldn't generate a response. Please try again."

        # Extract poster URLs
        posters = response.get("posters", [])
        if isinstance(posters, list):
            self._last_posters = [
                url for url in posters
                if isinstance(url, str) and url.startswith("http")
            ]
        else:
            logger.warning("Unexpected posters format: %s", type(posters))
            self._last_posters = []

        return response_text
