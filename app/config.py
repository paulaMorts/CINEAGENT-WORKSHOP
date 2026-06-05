"""Configuration module for CineAgent.

Loads application settings from environment variables and validates
that all required variables are present before the application starts.
Uses python-dotenv to load a .env file if present.
"""

import logging
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Required environment variable names
REQUIRED_ENV_VARS = ["OMDB_API_KEY", "AWS_REGION", "BEDROCK_MODEL_ID"]


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables."""

    omdb_api_key: str
    aws_region: str
    bedrock_model_id: str


def load_config() -> AppConfig:
    """Load configuration from environment variables.

    Loads a .env file if present (does not override existing env vars),
    then reads OMDB_API_KEY, AWS_REGION, and BEDROCK_MODEL_ID from the
    environment. If any required variable is missing or empty, logs an
    error specifying which variable is missing and terminates the
    application with exit code 1.

    Returns:
        AppConfig: A populated configuration instance.
    """
    # Load .env file if present (does not override existing env vars)
    load_dotenv()

    omdb_api_key = os.environ.get("OMDB_API_KEY", "")
    aws_region = os.environ.get("AWS_REGION", "")
    bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "")

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

    return AppConfig(
        omdb_api_key=omdb_api_key,
        aws_region=aws_region,
        bedrock_model_id=bedrock_model_id,
    )
