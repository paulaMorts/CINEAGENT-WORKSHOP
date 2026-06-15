"""
Setup script for AgentCore Memory.

Creates an AgentCore Memory resource for short-term conversation
storage. The memory stores per-session conversation turns so the
agent can recall context within a session.

Usage:
    python -m setup.setup_memory

Prerequisites:
    - AWS credentials configured (via .env or environment)

Output:
    Prints MEMORY_ID to copy into .env
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ----- Configuration -----

REGION = os.environ.get("AWS_REGION", "us-east-1")
MEMORY_NAME = "cineagent-session-memory"


def create_memory():
    """Create an AgentCore Memory resource for session storage."""

    print("=" * 60)
    print("  AgentCore Memory Setup - CineAgent Workshop")
    print("=" * 60)
    print()
    print(f"Region:      {REGION}")
    print(f"Memory name: {MEMORY_NAME}")
    print(f"Type:        Short-term conversation storage")
    print()

    try:
        # Create the AgentCore Memory client
        client = boto3.client("bedrock-agentcore-memory", region_name=REGION)

        print("Creating AgentCore Memory resource...")
        print()

        # Create the memory store configured for short-term conversation
        create_response = client.create_memory(
            name=MEMORY_NAME,
            description="CineAgent workshop session memory - stores conversation turns per session",
            memoryConfiguration={
                "shortTerm": {
                    "maxMessages": 20,
                    "description": "Short-term memory for CineAgent conversation sessions",
                }
            },
        )

        memory_id = create_response["memoryId"]

        # ----- Print results -----
        print("=" * 60)
        print("  SUCCESS! Memory resource created.")
        print("=" * 60)
        print()
        print("Add this value to your .env file:")
        print()
        print(f"  MEMORY_ID={memory_id}")
        print()
        print("=" * 60)

        return memory_id

    except NoCredentialsError:
        print("ERROR: AWS credentials not found.")
        print()
        print("Make sure you have configured AWS credentials:")
        print("  - Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN in .env")
        print("  - Or configure via 'aws configure'")
        sys.exit(1)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "AccessDeniedException":
            print(f"ERROR: Access denied - {error_message}")
            print()
            print("Your AWS credentials may not have permission to create AgentCore resources.")
            print("Check that your IAM role includes bedrock-agentcore permissions.")
        elif error_code == "ConflictException":
            print(f"ERROR: A memory resource named '{MEMORY_NAME}' already exists.")
            print()
            print("You can either:")
            print("  1. Delete the existing memory resource and re-run this script")
            print("  2. Use the existing memory ID from the AWS console")
        elif error_code == "ServiceQuotaExceededException":
            print(f"ERROR: Service quota exceeded - {error_message}")
            print()
            print("You have reached the maximum number of memory resources for your account.")
        else:
            print(f"ERROR: AWS API error [{error_code}]: {error_message}")

        sys.exit(1)

    except Exception as e:
        print(f"ERROR: Unexpected error - {e}")
        print()
        print("If the 'bedrock-agentcore-memory' service is not available,")
        print("check that you are using the correct AWS region and SDK version.")
        sys.exit(1)


if __name__ == "__main__":
    create_memory()
