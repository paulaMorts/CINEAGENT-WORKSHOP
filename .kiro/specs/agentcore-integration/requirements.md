# Requirements Document

## Introduction

This document defines the requirements for migrating the CineAgent conversational movie agent from direct boto3 Bedrock Converse API calls and in-memory session storage to AWS AgentCore. The migration replaces the internal agent execution logic with AgentCore Runtime, Gateway, Memory, and Observability services while preserving the existing Chainlit frontend, data layer, and user experience.

## Glossary

- **AgentCore_Runtime**: The AWS AgentCore Runtime service that manages agent execution, replacing direct boto3 Bedrock Converse API calls with a managed agent lifecycle.
- **AgentCore_Gateway**: The AWS AgentCore Gateway service that provides managed API tool calling, replacing direct httpx HTTP requests to external APIs.
- **AgentCore_Memory**: The AWS AgentCore Memory service that provides short-term memory for active conversations, replacing the in-memory Python dict-based session storage.
- **AgentCore_Observability**: The AWS AgentCore Observability service that provides tracing and monitoring for agent interactions.
- **CineAgent**: The conversational movie and TV series assistant application.
- **Runtime_Client**: The Python client module that communicates with AgentCore Runtime to send user messages and receive agent responses.
- **Gateway_Tool**: The tool configuration registered with AgentCore Gateway that proxies requests to the OMDb API.
- **Memory_Store**: The AgentCore Memory store instance that holds per-session conversation history.
- **Chainlit_Frontend**: The Chainlit-based chat UI that remains unchanged during this migration.
- **Data_Layer**: The JSON file-based conversation persistence component for the Chainlit UI sidebar that remains unchanged.
- **OMDb_API**: The Open Movie Database API used to retrieve movie and TV series metadata.
- **Session**: A single conversation between a user and CineAgent, identified by a unique session ID.

## Requirements

### Requirement 1: Agent Execution via AgentCore Runtime

**User Story:** As a workshop participant, I want CineAgent to execute through AgentCore Runtime, so that agent lifecycle management is handled by a managed AWS service instead of custom boto3 code.

#### Acceptance Criteria

1. WHEN a user sends a chat message, THE Runtime_Client SHALL forward the message to AgentCore_Runtime and return the agent response text to the caller.
2. THE Runtime_Client SHALL configure AgentCore_Runtime with the same system prompt currently defined in bedrock_client.py (CineAgent persona and rules).
3. THE Runtime_Client SHALL configure AgentCore_Runtime to use the anthropic.claude-3-haiku-20240307-v1:0 model on Bedrock.
4. WHEN AgentCore_Runtime returns a response, THE Runtime_Client SHALL extract the text content and return it as a string, maintaining the same interface as the current BedrockClient.process_message method.
5. IF AgentCore_Runtime returns an error or is unreachable, THEN THE Runtime_Client SHALL raise an exception that the existing error handling in main.py and api.py can catch.
6. THE Runtime_Client SHALL expose poster URLs collected during tool execution so the Chainlit handler can display movie poster images.

### Requirement 2: OMDb API Tool via AgentCore Gateway

**User Story:** As a workshop participant, I want the OMDb API tool to be called through AgentCore Gateway, so that external API integrations are managed by a centralized gateway service.

#### Acceptance Criteria

1. THE Gateway_Tool SHALL be registered with AgentCore_Gateway as a tool named "search_movie" with the same input schema (title parameter) as the current OMDb tool spec.
2. WHEN AgentCore_Runtime invokes the search_movie tool, THE Gateway_Tool SHALL forward the request to the OMDb API at http://www.omdbapi.com/ with the configured API key.
3. WHEN the OMDb API returns a successful response, THE Gateway_Tool SHALL return structured movie metadata (title, year, plot, genre, ratings, content_type, total_seasons, poster) to AgentCore_Runtime.
4. IF the OMDb API returns an error or times out, THEN THE Gateway_Tool SHALL return an error result with a descriptive message.
5. WHEN the OMDb API returns a poster URL, THE Gateway_Tool SHALL include the poster field in the response so it can be displayed in the UI.

### Requirement 3: Conversation Memory via AgentCore Memory

**User Story:** As a workshop participant, I want conversation history to be stored in AgentCore Memory, so that session state is managed by a dedicated service instead of an in-memory Python dictionary.

#### Acceptance Criteria

1. WHEN a new chat session starts, THE Memory_Store SHALL create a new memory context for the session identified by the session ID.
2. WHEN a user sends a message, THE Runtime_Client SHALL store the user message in AgentCore_Memory associated with the current session.
3. WHEN AgentCore_Runtime produces a response, THE Runtime_Client SHALL store the assistant response in AgentCore_Memory associated with the current session.
4. WHEN processing a new message, THE Runtime_Client SHALL retrieve the conversation history from AgentCore_Memory and include it as context for AgentCore_Runtime.
5. THE Memory_Store SHALL enforce a maximum of 20 messages per session, matching the current history limit.
6. IF AgentCore_Memory is unreachable, THEN THE Runtime_Client SHALL log a warning and continue processing the current message without historical context.

### Requirement 4: Tracing and Monitoring via AgentCore Observability

**User Story:** As a workshop participant, I want agent interactions traced through AgentCore Observability, so that I can monitor and debug the agent execution pipeline.

#### Acceptance Criteria

1. WHEN AgentCore_Runtime processes a message, THE AgentCore_Observability service SHALL capture a trace spanning the full request lifecycle (user message to final response).
2. THE AgentCore_Observability service SHALL record spans for each tool invocation (OMDb API calls via Gateway).
3. THE AgentCore_Observability service SHALL record the model ID and region used for each agent invocation.
4. IF tracing initialization fails, THEN THE CineAgent SHALL log a warning and continue operating without tracing.

### Requirement 5: Preserve Existing Frontend and User Experience

**User Story:** As a workshop participant, I want the migration to preserve the existing chat interface behavior, so that users see no difference in the CineAgent experience.

#### Acceptance Criteria

1. THE Chainlit_Frontend SHALL remain unchanged (app/main.py Chainlit handlers, UI configuration, authentication).
2. THE Data_Layer SHALL remain unchanged (app/data_layer.py JSON file-based persistence for conversation history sidebar).
3. WHEN a movie search returns poster URLs, THE CineAgent SHALL display poster images inline in the chat, matching the current behavior.
4. THE FastAPI /chat endpoint SHALL continue to function with the same request and response models (ChatRequest, ChatResponse).
5. THE CineAgent SHALL maintain the same conversational behavior (movie-only responses, tool usage for real data, recommendations with 3-5 titles).

### Requirement 6: Configuration and Environment Setup

**User Story:** As a workshop participant, I want the AgentCore configuration to follow the same pattern as the current environment variable loading, so that setup remains simple and consistent.

#### Acceptance Criteria

1. THE CineAgent SHALL load AgentCore-specific configuration (agent ID, gateway endpoint, memory endpoint) from environment variables.
2. THE CineAgent SHALL validate that all required AgentCore environment variables are present at startup, following the same pattern as the current config.py validation.
3. IF any required AgentCore environment variable is missing, THEN THE CineAgent SHALL log an error specifying the missing variable and terminate with exit code 1.
4. THE CineAgent SHALL continue to require the existing OMDB_API_KEY, AWS_REGION, and BEDROCK_MODEL_ID environment variables.

### Requirement 7: Dependency Management

**User Story:** As a workshop participant, I want the project dependencies updated to include the AgentCore SDK, so that the migration code has access to the required libraries.

#### Acceptance Criteria

1. THE requirements.txt SHALL include the AgentCore Python SDK package.
2. THE requirements.txt SHALL retain all existing dependencies (fastapi, uvicorn, chainlit, boto3, httpx, pydantic, python-dotenv, pytest, hypothesis, pytest-asyncio).
3. THE CineAgent SHALL remain compatible with Python 3.13.
