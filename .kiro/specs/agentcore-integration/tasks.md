# Implementation Plan: AgentCore Integration

## Overview

Migrate CineAgent from direct boto3 Bedrock Converse API calls to AWS AgentCore services. The implementation follows a sequential approach: first set up AWS infrastructure (Gateway, Memory), then create the agent code for Runtime deployment, build the local client replacement, update config/wiring, and finally validate with tests.

## Tasks

- [ ] 1. Update dependencies and environment configuration
  - [ ] 1.1 Update requirements.txt with AgentCore SDK packages
    - Add `bedrock-agentcore` and `strands-agents` to requirements.txt
    - Retain all existing dependencies (fastapi, uvicorn, chainlit, boto3, httpx, pydantic, python-dotenv, pytest, hypothesis, pytest-asyncio)
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 1.2 Extend AppConfig with AgentCore environment variables
    - Add new fields to the `AppConfig` dataclass: `agentcore_runtime_arn`, `agentcore_region`, `memory_id`, `gateway_url`, `gateway_access_token`
    - Update `REQUIRED_ENV_VARS` list to include the new AgentCore variables
    - Update `load_config()` to read and validate the new variables using the same pattern (log error + exit 1 if missing)
    - Keep existing fields (`omdb_api_key`, `aws_region`, `bedrock_model_id`) unchanged
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ] 1.3 Update .env.example with new AgentCore variables
    - Add placeholder entries for `AGENTCORE_RUNTIME_ARN`, `AGENTCORE_REGION`, `MEMORY_ID`, `GATEWAY_URL`, `GATEWAY_ACCESS_TOKEN`
    - Keep existing entries for `OMDB_API_KEY`, `AWS_REGION`, `BEDROCK_MODEL_ID`
    - _Requirements: 6.1_

- [ ] 2. Create AWS infrastructure setup scripts
  - [ ] 2.1 Create setup/setup_gateway.py script
    - Create the `setup/` directory
    - Write a script that creates an AgentCore Gateway resource with an OpenAPI target pointing at `http://www.omdbapi.com/`
    - Define the OpenAPI spec for the `search_movie` operation (GET with `t` query parameter)
    - Configure the OMDb API key as a query parameter credential
    - Print the Gateway URL and access token on success for the user to copy into `.env`
    - _Requirements: 2.1, 2.2_

  - [ ] 2.2 Create setup/setup_memory.py script
    - Write a script that creates an AgentCore Memory resource
    - Configure the memory store for short-term conversation storage
    - Print the Memory ID on success for the user to copy into `.env`
    - _Requirements: 3.1_

- [ ] 3. Checkpoint - Validate infrastructure setup
  - Ensure all tests pass, ask the user if questions arise.
  - User should run setup scripts and populate `.env` with the output values before proceeding.

- [ ] 4. Create the Strands Agent for AgentCore Runtime deployment
  - [ ] 4.1 Create agentcore_agent/entrypoint.py
    - Create the `agentcore_agent/` directory
    - Implement the Strands Agent using `BedrockAgentCoreApp` from `bedrock_agentcore.runtime`
    - Use `MemoryClient` from `bedrock_agentcore.memory` for session history
    - Configure the agent with the CineAgent system prompt (same as `SYSTEM_PROMPT` in bedrock_client.py)
    - Use `BedrockModel` from `strands.models` with `anthropic.claude-3-haiku-20240307-v1:0`
    - Connect Gateway tools via MCP for the `search_movie` tool
    - Implement the `@app.entrypoint` handler that accepts `{"prompt": str, "session_id": str}` payload
    - Store conversation turns in Memory after each interaction (user + assistant messages)
    - Retrieve last 10 turns from Memory before invoking the agent for context
    - Return `{"response": str, "posters": list[str]}` payload
    - Handle Memory failures gracefully: log warning, continue without history
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.3, 2.4, 2.5, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1, 4.2, 4.3, 4.4_

  - [ ] 4.2 Create agentcore_agent/requirements.txt
    - Add agent-specific dependencies: `strands-agents`, `bedrock-agentcore`, `boto3`
    - This file is used by AgentCore Runtime when deploying the agent
    - _Requirements: 7.1_

- [ ] 5. Create the AgentCoreClient (replaces BedrockClient)
  - [ ] 5.1 Create app/agentcore_client.py
    - Implement `AgentCoreClient` class with `__init__(self, runtime_arn: str, region: str)`
    - Implement `async process_message(self, query: str, session_id: str) -> str` method
    - Use `AgentCoreRuntimeClient` from the `bedrock-agentcore` SDK to invoke the deployed agent
    - Send `{"prompt": query, "session_id": session_id}` as the invocation payload
    - Parse the response to extract `response` text and `posters` list
    - Expose `last_posters` property (list of poster URLs from the most recent invocation)
    - Raise `ConnectionError` when Runtime is unreachable
    - Raise `RuntimeError` with descriptive message on Runtime errors
    - Raise `TimeoutError` on timeout scenarios
    - Validate session_id format before calling Runtime
    - _Requirements: 1.1, 1.4, 1.5, 1.6, 5.4_

- [ ] 6. Wire AgentCoreClient into main.py and api.py
  - [ ] 6.1 Update app/main.py to use AgentCoreClient
    - Replace `BedrockClient` import and instantiation with `AgentCoreClient`
    - Instantiate `AgentCoreClient(runtime_arn=config.agentcore_runtime_arn, region=config.agentcore_region)`
    - Remove `OMDbTool` initialization (no longer needed locally — Gateway handles it)
    - Update `set_bedrock_client()` call to pass the new client (interface-compatible)
    - Keep poster extraction logic unchanged (`client.last_posters`)
    - Keep all Chainlit handlers unchanged (on_chat_start, on_message, header_auth_callback)
    - Keep DataLayer initialization unchanged
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 6.2 Update app/api.py type hints
    - Change the type annotation from `BedrockClient` to `AgentCoreClient` (or use a Protocol/Union)
    - Verify the `/chat` endpoint still works with the new client's `process_message` interface
    - Keep timeout logic (30s `asyncio.wait_for`) unchanged
    - _Requirements: 5.4_

- [ ] 7. Checkpoint - Local integration validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify the app starts without errors with correct `.env` values.

- [ ] 8. Write unit tests for new components
  - [ ] 8.1 Write unit tests for AgentCoreClient
    - Test `process_message()` with mocked `AgentCoreRuntimeClient` returning a valid response
    - Test response parsing: text extraction and poster URL extraction
    - Test error handling: mock `ConnectionError`, `RuntimeError`, `TimeoutError`
    - Test graceful handling of malformed responses (missing keys, empty response)
    - Test `last_posters` property returns URLs from the most recent call
    - Test session_id validation
    - _Requirements: 1.1, 1.4, 1.5, 1.6_

  - [ ] 8.2 Write unit tests for updated config.py
    - Test `load_config()` with all AgentCore env vars present → returns populated AppConfig
    - Test `load_config()` with missing AgentCore env vars → logs error and exits
    - Test that existing env vars (OMDB_API_KEY, AWS_REGION, BEDROCK_MODEL_ID) still validated
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ] 8.3 Write smoke tests for dependencies and constants
    - Test that `requirements.txt` contains `bedrock-agentcore` and `strands-agents`
    - Test that the system prompt in `agentcore_agent/entrypoint.py` matches expected value
    - Test that model ID configuration uses `anthropic.claude-3-haiku-20240307-v1:0`
    - _Requirements: 1.2, 1.3, 7.1_

- [ ] 9. Deploy agent to AgentCore Runtime
  - [ ] 9.1 Create deployment script setup/deploy_agent.py
    - Write a script that packages `agentcore_agent/` and deploys to AgentCore Runtime
    - Use the `bedrock-agentcore` SDK deployment utilities
    - Print the Runtime ARN on success for the user to populate in `.env`
    - Include instructions for updating `AGENTCORE_RUNTIME_ARN` after deployment
    - _Requirements: 1.1_

- [ ] 10. Final checkpoint - End-to-end validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify end-to-end: send a movie query via Chainlit UI → get response with poster images.
  - Confirm conversation memory persists across messages in the same session.

## Notes

- This is a workshop project — scripts print output values for manual `.env` population rather than auto-configuring
- The existing `app/bedrock_client.py` and `app/omdb_tool.py` are kept for reference but no longer used in the production path
- Integration tests with real AWS services are run manually during the workshop (require credentials)
- The `AgentCoreClient` maintains the same interface as `BedrockClient` to minimize changes in `main.py` and `api.py`
- AgentCore Observability tracing is automatic for Runtime-hosted agents — no code needed
- Property-based testing is not applicable for this infrastructure migration feature

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["4.1", "4.2", "5.1"] },
    { "id": 3, "tasks": ["6.1", "6.2"] },
    { "id": 4, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 5, "tasks": ["9.1"] }
  ]
}
```
