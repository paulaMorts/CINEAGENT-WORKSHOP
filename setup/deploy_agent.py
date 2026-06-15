"""
Deploy CineAgent to AgentCore Runtime.

Packages the agentcore_agent/ directory and deploys it to AgentCore Runtime.
On success, prints the Runtime ARN to copy into your .env file.

Usage:
    python -m setup.deploy_agent

Prerequisites:
    - AWS credentials configured (via .env or environment)
    - MEMORY_ID, GATEWAY_URL, GATEWAY_ACCESS_TOKEN set in .env
    - The agentcore_agent/ directory exists with entrypoint.py and requirements.txt

Output:
    Prints AGENTCORE_RUNTIME_ARN to add to .env
"""

import io
import os
import sys
import zipfile

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load .env from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ----- Configuration -----

REGION = os.environ.get("AWS_REGION", "us-east-1")
MEMORY_ID = os.environ.get("MEMORY_ID", "")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
GATEWAY_ACCESS_TOKEN = os.environ.get("GATEWAY_ACCESS_TOKEN", "")
AGENT_NAME = "cineagent-runtime-agent"

# Path to the agent source directory
AGENT_DIR = os.path.join(os.path.dirname(__file__), "..", "agentcore_agent")


def package_agent(agent_dir: str) -> bytes:
    """Package the agent directory into a zip archive (in memory).

    Args:
        agent_dir: Path to the agentcore_agent/ directory.

    Returns:
        The zip file contents as bytes.
    """
    buffer = io.BytesIO()
    agent_dir = os.path.abspath(agent_dir)

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(agent_dir):
            for filename in files:
                # Skip __pycache__ and hidden files
                if "__pycache__" in root or filename.startswith("."):
                    continue
                filepath = os.path.join(root, filename)
                arcname = os.path.relpath(filepath, agent_dir)
                zf.write(filepath, arcname)
                print(f"  Added: {arcname}")

    return buffer.getvalue()


def deploy_agent():
    """Package and deploy the CineAgent to AgentCore Runtime."""

    # ----- Validate prerequisites -----
    if not MEMORY_ID:
        print("ERROR: MEMORY_ID is not set in environment or .env file.")
        print("Run 'python -m setup.setup_memory' first to create a Memory resource.")
        sys.exit(1)

    if not GATEWAY_URL or not GATEWAY_ACCESS_TOKEN:
        print("ERROR: GATEWAY_URL and GATEWAY_ACCESS_TOKEN are not set.")
        print("Run 'python -m setup.setup_gateway' first to create a Gateway resource.")
        sys.exit(1)

    if not os.path.isdir(AGENT_DIR):
        print(f"ERROR: Agent directory not found: {AGENT_DIR}")
        print("Make sure the agentcore_agent/ directory exists with entrypoint.py.")
        sys.exit(1)

    entrypoint_path = os.path.join(AGENT_DIR, "entrypoint.py")
    if not os.path.isfile(entrypoint_path):
        print(f"ERROR: entrypoint.py not found in {AGENT_DIR}")
        sys.exit(1)

    print("=" * 60)
    print("  AgentCore Runtime Deployment - CineAgent Workshop")
    print("=" * 60)
    print()
    print(f"Region:     {REGION}")
    print(f"Agent name: {AGENT_NAME}")
    print(f"Source dir: {os.path.abspath(AGENT_DIR)}")
    print()

    # ----- Package the agent -----
    print("Packaging agent code...")
    zip_bytes = package_agent(AGENT_DIR)
    print(f"  Package size: {len(zip_bytes)} bytes")
    print()

    # ----- Deploy to AgentCore Runtime -----
    try:
        client = boto3.client("bedrock-agentcore", region_name=REGION)

        print("Deploying to AgentCore Runtime...")
        print()

        # Environment variables the agent needs at runtime
        agent_env_vars = {
            "MEMORY_ID": MEMORY_ID,
            "GATEWAY_URL": GATEWAY_URL,
            "GATEWAY_ACCESS_TOKEN": GATEWAY_ACCESS_TOKEN,
        }

        # Create or update the agent on Runtime
        try:
            # Try to create a new agent
            response = client.create_runtime_agent(
                name=AGENT_NAME,
                description="CineAgent - Movie and TV series assistant (workshop deployment)",
                agentCode=zip_bytes,
                entrypoint="entrypoint.invoke",
                environmentVariables=agent_env_vars,
            )
            runtime_arn = response["agentRuntimeArn"]
            print(f"  Agent created successfully!")

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ConflictException":
                # Agent already exists — update it
                print("  Agent already exists, updating...")
                response = client.update_runtime_agent(
                    name=AGENT_NAME,
                    description="CineAgent - Movie and TV series assistant (workshop deployment)",
                    agentCode=zip_bytes,
                    entrypoint="entrypoint.invoke",
                    environmentVariables=agent_env_vars,
                )
                runtime_arn = response["agentRuntimeArn"]
                print(f"  Agent updated successfully!")
            else:
                raise

        # ----- Print results -----
        print()
        print("=" * 60)
        print("  SUCCESS! Agent deployed to AgentCore Runtime.")
        print("=" * 60)
        print()
        print("Add this value to your .env file:")
        print()
        print(f"  AGENTCORE_RUNTIME_ARN={runtime_arn}")
        print()
        print("Also add the region if not already set:")
        print()
        print(f"  AGENTCORE_REGION={REGION}")
        print()
        print("After updating .env, restart the Chainlit app to use the deployed agent.")
        print()
        print("=" * 60)

        return runtime_arn

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
            print("Your AWS credentials may not have permission to deploy agents.")
            print("Check that your IAM role includes bedrock-agentcore permissions.")
        elif error_code == "ServiceQuotaExceededException":
            print(f"ERROR: Service quota exceeded - {error_message}")
            print()
            print("You have reached the maximum number of runtime agents for your account.")
        elif error_code == "ValidationException":
            print(f"ERROR: Validation error - {error_message}")
            print()
            print("Check your agent code and configuration.")
        else:
            print(f"ERROR: AWS API error [{error_code}]: {error_message}")

        sys.exit(1)

    except Exception as e:
        print(f"ERROR: Unexpected error - {e}")
        print()
        print("If the 'bedrock-agentcore' service is not available,")
        print("check that you are using the correct AWS region and SDK version.")
        sys.exit(1)


if __name__ == "__main__":
    deploy_agent()
