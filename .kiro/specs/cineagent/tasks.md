# Implementation Plan: CineAgent

## Overview

Implement a conversational movie and TV series recommendation agent using Python with FastAPI, Chainlit, Amazon Bedrock (Converse API), and the OMDb API. The implementation follows an incremental approach: configuration and models first, then core components (OMDb tool, Bedrock client, FastAPI endpoints), then the Chainlit frontend, and finally wiring everything together.

## Tasks

- [ ] 1. Set up project structure, dependencies, and configuration
  - [x] 1.1 Create project structure and install dependencies
    - Create the project directory structure: `app/`, `tests/`
    - Create `requirements.txt` with dependencies: fastapi, uvicorn, chainlit, boto3, httpx, pydantic, python-dotenv, pytest, hypothesis, pytest-asyncio
    - Create `.env.example` documenting required environment variables (OMDB_API_KEY, AWS_REGION, BEDROCK_MODEL_ID)
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 1.2 Implement configuration module (`app/config.py`)
    - Create `AppConfig` dataclass with fields: `omdb_api_key`, `aws_region`, `bedrock_model_id`
    - Implement `load_config()` that reads from environment variables
    - If any required variable is missing or empty, log an error specifying which variable is missing and call `sys.exit(1)`
    - If all variables are present and non-empty, return a populated `AppConfig` instance
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 1.3 Write property test for configuration validation
    - **Property 7: Configuration validation at startup**
    - **Validates: Requirements 7.4, 7.5**
    - Generate combinations of present/missing/empty env vars using Hypothesis
    - Verify startup succeeds if and only if all three are present and non-empty
    - Verify error message specifies the missing variable

  - [ ] 1.4 Create data models (`app/models.py`)
    - Implement `ChatRequest` Pydantic model with `query` (min_length=1, max_length=2000) and `session_id` (min_length=1, max_length=128)
    - Implement `ChatResponse` Pydantic model with `response` and `session_id` fields
    - Implement `ErrorResponse` Pydantic model with `error` and optional `detail` fields
    - Implement `OMDbResult` dataclass with fields: success, title, year, plot, genre, ratings, content_type, total_seasons, error
    - _Requirements: 2.1, 2.4, 4.2_

- [ ] 2. Implement OMDb Tool
  - [ ] 2.1 Implement OMDb tool (`app/omdb_tool.py`)
    - Create `OMDbTool` class with `__init__(self, api_key: str, timeout: float = 10.0)`
    - Implement `async def search_by_title(self, title: str) -> OMDbResult`
    - Validate that title is not empty or whitespace-only; return error `OMDbResult` without making HTTP call if invalid
    - Query OMDb API via HTTP GET with `t` parameter and API key
    - On success (`Response: "True"`): extract title, year, plot, genre, ratings, type, and totalSeasons (when type is "series")
    - On "not found" (`Response: "False"`): return `OMDbResult(success=False, error="...")` indicating no match
    - On timeout (>10s) or HTTP error: return `OMDbResult(success=False, error="...")` with failure reason
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 6.3_

  - [ ]* 2.2 Write property test for empty/blank title rejection
    - **Property 6: Empty or blank title rejection**
    - **Validates: Requirements 4.5**
    - Generate whitespace-only strings using Hypothesis
    - Verify error result returned without any HTTP request

  - [ ]* 2.3 Write property test for OMDb response extraction
    - **Property 5: OMDb response extraction completeness**
    - **Validates: Requirements 4.2, 6.3**
    - Generate valid OMDb JSON responses using Hypothesis strategies
    - Verify all fields are extracted; verify totalSeasons extracted when type is "series"

  - [ ]* 2.4 Write unit tests for OMDb tool
    - Test successful movie lookup with mocked HTTP response
    - Test "Movie not found!" scenario
    - Test timeout handling (10s)
    - Test HTTP error handling
    - _Requirements: 4.1, 4.3, 4.4_

- [ ] 3. Implement Bedrock Client
  - [ ] 3.1 Implement Bedrock client (`app/bedrock_client.py`)
    - Create `BedrockClient` class with `__init__(self, region: str, model_id: str)`
    - Initialize boto3 Bedrock Runtime client
    - Define system prompt establishing CineAgent as a movie/TV assistant and rejecting off-topic queries
    - Define `OMDB_TOOL_SPEC` for the Converse API tool configuration
    - Implement in-memory session storage: `dict[str, list[dict]]`
    - Implement `async def process_message(self, query: str, session_id: str) -> str`
    - Build message list from session history, add user query
    - Call Bedrock Converse API with system prompt, messages, and tool config
    - If stop reason is `tool_use`: extract tool name and input, call OMDb tool, send tool result back to Bedrock
    - If stop reason is `end_of_turn`: extract and return assistant text
    - Enforce conversation history limit of 20 messages (keep most recent)
    - Store both user and assistant messages in session history
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.1, 5.2, 5.3, 6.1, 6.2, 6.4_

  - [ ]* 3.2 Write property test for system prompt inclusion
    - **Property 3: System prompt always included**
    - **Validates: Requirements 3.1**
    - Generate random queries using Hypothesis
    - Mock boto3 Converse API call and assert system prompt is always present

  - [ ]* 3.3 Write property test for session history bound
    - **Property 4: Session history bounded at 20 messages**
    - **Validates: Requirements 3.4**
    - Generate message sequences > 20 using Hypothesis
    - Verify history never exceeds 20 messages, most recent are preserved

  - [ ]* 3.4 Write unit tests for Bedrock client
    - Test tool-use dispatch: mock Bedrock returning `tool_use` stop reason, verify OMDb tool is called
    - Test end_of_turn response extraction
    - Test off-topic rejection behavior
    - _Requirements: 3.2, 3.3, 3.5_

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement FastAPI endpoints and error handling
  - [ ] 5.1 Implement FastAPI application (`app/api.py`)
    - Create FastAPI app instance
    - Implement `POST /chat` endpoint accepting `ChatRequest`, returning `ChatResponse`
    - On valid request: call `BedrockClient.process_message()` with query and session_id
    - Add 30-second timeout around the Bedrock client call
    - On timeout: return HTTP 503 with message "AI service temporarily unavailable"
    - On Bedrock connection error: return HTTP 503 with safe message
    - On unexpected error: log full details (timestamp, error type), return HTTP 500 with generic message
    - Ensure no error response exposes stack traces, file paths, or credentials
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 5.2 Write property test for request validation
    - **Property 1: Request validation accepts valid inputs and rejects invalid inputs**
    - **Validates: Requirements 2.1, 2.4**
    - Generate random strings of varying lengths using Hypothesis
    - Verify acceptance when query is 1-2000 chars and session_id is 1-128 chars
    - Verify HTTP 422 rejection otherwise

  - [ ]* 5.3 Write property test for response pass-through
    - **Property 2: Valid request-response pass-through**
    - **Validates: Requirements 2.2, 2.3**
    - Generate valid requests and mock response strings using Hypothesis
    - Verify exact response text and session_id pass-through

  - [ ]* 5.4 Write property test for error response safety
    - **Property 8: Error responses never expose internal details**
    - **Validates: Requirements 8.3, 8.4**
    - Generate various exceptions using Hypothesis
    - Verify no stack traces, file paths, or credentials in response body

  - [ ]* 5.5 Write unit tests for API endpoints
    - Test valid request returns 200 with correct response
    - Test missing query returns 422
    - Test query exceeding 2000 chars returns 422
    - Test 30-second timeout returns 503
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

- [ ] 6. Implement Chainlit frontend
  - [ ] 6.1 Implement Chainlit application (`app/main.py`)
    - Create the main application entry point that mounts Chainlit on FastAPI
    - Implement `@cl.on_message` handler that sends user query to `/chat` endpoint
    - Display assistant response in the chat thread
    - Show loading indicator while waiting for response
    - Generate and maintain session_id per user session
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 7. Wire components together and integration testing
  - [ ] 7.1 Wire all components in the main entry point
    - In `app/main.py`: load config, initialize OMDb tool with API key, initialize Bedrock client with region and model ID
    - Mount Chainlit as sub-application on FastAPI
    - Ensure the API endpoint has access to the initialized Bedrock client and OMDb tool
    - Add startup validation (config check) before accepting requests
    - _Requirements: 7.4, 7.5_

  - [ ]* 7.2 Write integration tests
    - Test end-to-end flow: user query → FastAPI → mocked Bedrock → mocked OMDb → response
    - Test recommendation flow: query for recommendations → OMDb lookup → response with suggestions
    - Test TV series labeling: query about TV series, verify content type in response
    - _Requirements: 1.3, 2.2, 2.3, 3.2, 3.3, 5.1, 6.1_

- [ ] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with FastAPI, Chainlit, boto3, and httpx as specified in the design
- All code should be simple and didactic, appropriate for a workshop setting

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.4"] },
    { "id": 2, "tasks": ["1.3", "2.1"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "3.1"] },
    { "id": 4, "tasks": ["3.2", "3.3", "3.4", "5.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.4", "5.5", "6.1"] },
    { "id": 6, "tasks": ["7.1"] },
    { "id": 7, "tasks": ["7.2"] }
  ]
}
```
