"""Configuration module for CineAgent.

Loads application settings from environment variables and validates
that all required variables are present before the application starts.
Uses python-dotenv to load a .env file if present.

AgentCore variables are optional — if not set, the app falls back
to the direct BedrockClient mode (no AgentCore).
"""

import logging
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Required environment variable names (core app)
REQUIRED_ENV_VARS = ["OMDB_API_KEY", "AWS_REGION", "BEDROCK_MODEL_ID"]

# Optional AgentCore variables (if all are set, AgentCore mode is used)
AGENTCORE_ENV_VARS = [
    "AGENTCORE_RUNTIME_ARN",
    "AGENTCORE_REGION",
    "MEMORY_ID",
    "GATEWAY_URL",
    "GATEWAY_ACCESS_TOKEN",
]


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables."""

    # Required
    omdb_api_key: str
    aws_region: str
    bedrock_model_id: str

    # Optional AgentCore settings (empty string = not configured)
    agentcore_runtime_arn: str = ""
    agentcore_region: str = ""
    memory_id: str = ""
    gateway_url: str = ""
    gateway_access_token: str = ""

    @property
    def use_agentcore(self) -> bool:
        """Whether AgentCore mode is enabled (core AgentCore vars are set)."""
        return bool(
            self.agentcore_runtime_arn
            and self.agentcore_region
            and self.memory_id
            and self.gateway_url
        )


def load_config() -> AppConfig:
    """Load configuration from environment variables.

    Loads a .env file if present (does not override existing env vars),
    then reads required variables from the environment. If any required
    variable is missing or empty, logs an error and terminates.

    AgentCore variables are optional — if not all are set, the app
    runs in direct Bedrock mode.

    Returns:
        AppConfig: A populated configuration instance.
    """
    # Load .env file if present (does not override existing env vars)
    load_dotenv()

    omdb_api_key = os.environ.get("OMDB_API_KEY", "")
    aws_region = os.environ.get("AWS_REGION", "")
    bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "")

    # Validate required vars
    missing = []
    if not omdb_api_key:
        missing.append("OMDB_API_KEY")
    if not aws_region:
        missing.append("AWS_REGION")
    if not bedrock_model_id:
        missing.append("BEDROCK_MODEL_ID")

    if missing:
        for var in missing:
            logger.error(
                "Required environment variable %s is missing or empty", var
            )
        sys.exit(1)

    # Read optional AgentCore vars
    agentcore_runtime_arn = os.environ.get("AGENTCORE_RUNTIME_ARN", "")
    agentcore_region = os.environ.get("AGENTCORE_REGION", "")
    memory_id = os.environ.get("MEMORY_ID", "")
    gateway_url = os.environ.get("GATEWAY_URL", "")
    gateway_access_token = os.environ.get("GATEWAY_ACCESS_TOKEN", "")

    config = AppConfig(
        omdb_api_key=omdb_api_key,
        aws_region=aws_region,
        bedrock_model_id=bedrock_model_id,
        agentcore_runtime_arn=agentcore_runtime_arn,
        agentcore_region=agentcore_region,
        memory_id=memory_id,
        gateway_url=gateway_url,
        gateway_access_token=gateway_access_token,
    )

    if config.use_agentcore:
        logger.info("AgentCore mode enabled")
    else:
        logger.info("Direct Bedrock mode (AgentCore not configured)")

    return config
