"""
Setup script for AgentCore Gateway.

Creates an AgentCore Gateway resource with an OpenAPI target
pointing at the OMDb API (http://www.omdbapi.com/).

The Gateway proxies the search_movie tool call and injects the
OMDb API key as a query parameter credential.

Usage:
    python -m setup.setup_gateway

Prerequisites:
    - AWS credentials configured (via .env or environment)
    - OMDB_API_KEY set in .env or environment

Output:
    Prints GATEWAY_URL and GATEWAY_ACCESS_TOKEN to copy into .env
"""

import json
import os
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ----- Configuration -----

REGION = os.environ.get("AWS_REGION", "us-east-1")
OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")
GATEWAY_NAME = "cineagent-omdb-gateway"

# OpenAPI spec for the OMDb API target
OMDB_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "OMDb API", "version": "1.0.0"},
    "servers": [{"url": "http://www.omdbapi.com"}],
    "paths": {
        "/": {
            "get": {
                "operationId": "search_movie",
                "summary": "Search for a movie or TV series by title",
                "parameters": [
                    {
                        "name": "t",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Title of the movie or TV series to search for",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Movie/series metadata",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    }
                },
            }
        }
    },
}


def create_gateway():
    """Create an AgentCore Gateway with OMDb OpenAPI target."""

    # ----- Validate prerequisites -----
    if not OMDB_API_KEY:
        print("ERROR: OMDB_API_KEY is not set in environment or .env file.")
        print("Please set it before running this script.")
        sys.exit(1)

    print("=" * 60)
    print("  AgentCore Gateway Setup - CineAgent Workshop")
    print("=" * 60)
    print()
    print(f"Region:       {REGION}")
    print(f"Gateway name: {GATEWAY_NAME}")
    print(f"Target URL:   http://www.omdbapi.com/")
    print()

    try:
        # Create the AgentCore Gateway client
        client = boto3.client("bedrock-agentcore-gateway", region_name=REGION)

        print("Creating AgentCore Gateway...")
        print()

        # Step 1: Create the Gateway resource
        create_response = client.create_gateway(
            name=GATEWAY_NAME,
            description="CineAgent workshop gateway - proxies OMDb API calls with API key injection",
        )

        gateway_id = create_response["gatewayId"]
        print(f"  Gateway created: {gateway_id}")

        # Step 2: Create the API target with OpenAPI spec
        print("  Adding OMDb API target...")

        target_response = client.create_target(
            gatewayId=gateway_id,
            name="omdb-api-target",
            description="OMDb movie database API",
            targetConfiguration={
                "openApi": {
                    "spec": json.dumps(OMDB_OPENAPI_SPEC),
                }
            },
            credentialConfiguration={
                "queryParameter": {
                    "parameterName": "apikey",
                    "value": OMDB_API_KEY,
                }
            },
        )

        target_id = target_response["targetId"]
        print(f"  Target created: {target_id}")

        # Step 3: Retrieve Gateway URL and access token
        print("  Retrieving Gateway endpoint details...")

        gateway_info = client.get_gateway(gatewayId=gateway_id)
        gateway_url = gateway_info.get("gatewayUrl", "")

        # Get access token for the gateway
        token_response = client.create_gateway_access_token(
            gatewayId=gateway_id,
            name="cineagent-workshop-token",
        )
        access_token = token_response.get("accessToken", "")

        # ----- Print results -----
        print()
        print("=" * 60)
        print("  SUCCESS! Gateway created.")
        print("=" * 60)
        print()
        print("Add these values to your .env file:")
        print()
        print(f"  GATEWAY_URL={gateway_url}")
        print(f"  GATEWAY_ACCESS_TOKEN={access_token}")
        print()
        print("=" * 60)

        return gateway_url, access_token

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
            print(f"ERROR: A gateway named '{GATEWAY_NAME}' already exists.")
            print()
            print("You can either:")
            print("  1. Delete the existing gateway and re-run this script")
            print("  2. Use the existing gateway's URL and token from the AWS console")
        elif error_code == "ServiceQuotaExceededException":
            print(f"ERROR: Service quota exceeded - {error_message}")
            print()
            print("You have reached the maximum number of gateways for your account.")
        else:
            print(f"ERROR: AWS API error [{error_code}]: {error_message}")

        sys.exit(1)

    except Exception as e:
        print(f"ERROR: Unexpected error - {e}")
        print()
        print("If the 'bedrock-agentcore-gateway' service is not available,")
        print("check that you are using the correct AWS region and SDK version.")
        sys.exit(1)


if __name__ == "__main__":
    create_gateway()
