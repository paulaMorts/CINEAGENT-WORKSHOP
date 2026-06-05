# Requirements Document

## Introduction

CineAgent is a conversational movie and TV series recommendation agent built for an AWS workshop demonstrating Kiro IDE and Kiro CLI capabilities. The agent uses a Chainlit frontend, a Python/FastAPI backend, Amazon Bedrock as the conversational AI model, and the OMDb API as a tool for searching movie and TV series information. The architecture follows a simple, didactic flow: User → Chainlit → FastAPI → Amazon Bedrock → OMDb API → Final answer.

## Glossary

- **CineAgent**: The conversational movie and TV series agent application
- **Chainlit_Frontend**: The web-based chat interface that users interact with to send queries and receive responses
- **FastAPI_Backend**: The Python web server that receives requests from the frontend and orchestrates calls to Amazon Bedrock and OMDb API
- **Bedrock_Client**: The component that communicates with Amazon Bedrock to process natural language queries and generate conversational responses
- **OMDb_Tool**: The component that queries the OMDb API to retrieve movie and TV series information such as title, plot, ratings, and metadata
- **Conversation_Session**: A single user chat session that maintains message history for contextual responses
- **Query**: A natural language message sent by the user requesting movie or TV series information or recommendations

## Requirements

### Requirement 1: Chat Interface

**User Story:** As a workshop participant, I want a web-based chat interface, so that I can interact with CineAgent using natural language.

#### Acceptance Criteria

1. THE Chainlit_Frontend SHALL display a chat input field where users can type queries
2. WHEN a user submits a Query, THE Chainlit_Frontend SHALL display the user message in the conversation thread
3. WHEN the FastAPI_Backend returns a response, THE Chainlit_Frontend SHALL display the agent response in the conversation thread
4. WHILE the FastAPI_Backend is processing a Query, THE Chainlit_Frontend SHALL display a loading indicator to the user

### Requirement 2: API Request Handling

**User Story:** As a developer, I want the FastAPI backend to receive chat messages and return agent responses, so that the frontend and AI logic are decoupled.

#### Acceptance Criteria

1. THE FastAPI_Backend SHALL expose a POST endpoint that accepts a JSON body containing a Query (non-empty string, maximum 2000 characters) and a session identifier (non-empty string, maximum 128 characters)
2. WHEN a request is received with a non-empty Query of 2000 characters or fewer and a non-empty session identifier, THE FastAPI_Backend SHALL forward the Query and session identifier to the Bedrock_Client for processing
3. WHEN the Bedrock_Client returns a response, THE FastAPI_Backend SHALL return the response text and the session identifier to the Chainlit_Frontend within 30 seconds of receiving the original request
4. IF the FastAPI_Backend receives a malformed request (missing Query, empty Query, Query exceeding 2000 characters, missing session identifier, or invalid JSON), THEN THE FastAPI_Backend SHALL return an HTTP 422 error with a message indicating which field failed validation
5. IF the Bedrock_Client does not return a response within 30 seconds, THEN THE FastAPI_Backend SHALL return an error message indicating the request timed out

### Requirement 3: Conversational AI Processing

**User Story:** As a workshop participant, I want the agent to understand my movie-related questions and respond in natural language, so that I get helpful and contextual answers.

#### Acceptance Criteria

1. WHEN a Query is forwarded to the Bedrock_Client, THE Bedrock_Client SHALL send the Query along with a system prompt defining CineAgent as a movie and TV series assistant to Amazon Bedrock
2. WHEN Amazon Bedrock determines that movie or TV series data is needed, THE Bedrock_Client SHALL invoke the OMDb_Tool to retrieve the requested information
3. WHEN the OMDb_Tool returns results, THE Bedrock_Client SHALL incorporate the retrieved data into a human-readable response that references the specific title, year, and relevant metadata returned by the OMDb_Tool
4. THE Bedrock_Client SHALL maintain conversation history within a Conversation_Session by storing both user queries and assistant responses, up to a maximum of 20 messages, to provide follow-up responses that reference prior exchanges in the same session
5. IF a Query is not related to movies or TV series, THEN THE Bedrock_Client SHALL respond indicating that CineAgent only handles movie and TV series topics and suggest the user ask a movie-related question

### Requirement 4: OMDb API Integration

**User Story:** As a workshop participant, I want the agent to search for real movie and TV series data, so that I receive accurate information about titles, plots, and ratings.

#### Acceptance Criteria

1. WHEN the Bedrock_Client requests a movie or TV series search, THE OMDb_Tool SHALL query the OMDb API by title with a maximum response timeout of 10 seconds
2. WHEN the OMDb API returns results, THE OMDb_Tool SHALL extract title, year, plot, genre, ratings, and type (movie or series) from the response
3. IF the OMDb API returns no results for a search query, THEN THE OMDb_Tool SHALL return a structured response indicating that no matching title was found for the given search term
4. IF the OMDb API does not respond within 10 seconds or returns an error, THEN THE OMDb_Tool SHALL return an error message to the Bedrock_Client indicating the failure reason (timeout, HTTP error, or API error)
5. IF the Bedrock_Client provides an empty or blank title for search, THEN THE OMDb_Tool SHALL return an error indicating that a non-empty title is required without making an API call

### Requirement 5: Movie Recommendations

**User Story:** As a workshop participant, I want to ask for movie recommendations similar to a given title, so that I can discover new movies based on my preferences.

#### Acceptance Criteria

1. WHEN a user asks for recommendations similar to a specific title, THE Bedrock_Client SHALL retrieve the genre, plot, and metadata of the referenced title from the OMDb_Tool and generate between 3 and 5 suggestions that share genre, themes, or narrative style with the referenced title
2. WHEN generating recommendations, THE Bedrock_Client SHALL include the title and release year of each recommended movie and explain why each recommendation is similar to the referenced title
3. IF the referenced title is not found by the OMDb_Tool, THEN THE Bedrock_Client SHALL inform the user that the title could not be found and ask the user to verify the title name

### Requirement 6: TV Series Search and Recommendations

**User Story:** As a workshop participant, I want to search for and get recommendations about TV series, so that the agent covers both movies and TV content.

#### Acceptance Criteria

1. WHEN a user asks about TV series, THE Bedrock_Client SHALL explicitly label the content type as "movie" or "series" in the response for each title mentioned
2. WHEN a user requests short TV series recommendations, THE Bedrock_Client SHALL recommend series with 3 or fewer seasons or limited-series formats and SHALL list each recommended series along with its season count
3. WHEN the OMDb_Tool retrieves TV series data, THE OMDb_Tool SHALL include the number of seasons in the extracted metadata
4. IF the user asks about a TV series but the OMDb_Tool returns a result with type "movie" instead of "series", THEN THE Bedrock_Client SHALL inform the user that the found title is a movie and offer to search for TV series alternatives

### Requirement 7: Environment Configuration

**User Story:** As a developer, I want the application to read configuration from environment variables, so that API keys and model settings are not hardcoded.

#### Acceptance Criteria

1. THE FastAPI_Backend SHALL read the OMDb API key from an environment variable named OMDB_API_KEY
2. THE Bedrock_Client SHALL read the AWS region from an environment variable named AWS_REGION
3. THE Bedrock_Client SHALL read the Bedrock model identifier from an environment variable named BEDROCK_MODEL_ID
4. IF a required environment variable (OMDB_API_KEY, AWS_REGION, or BEDROCK_MODEL_ID) is missing or set to an empty string at application startup, THEN THE FastAPI_Backend SHALL log an error message specifying which variable is missing and terminate with a non-zero exit code
5. IF all required environment variables are present and non-empty at startup, THEN THE FastAPI_Backend SHALL complete initialization and begin accepting requests

### Requirement 8: Error Handling and User Feedback

**User Story:** As a workshop participant, I want clear error messages when something goes wrong, so that I understand what happened and can try again.

#### Acceptance Criteria

1. IF the Bedrock_Client fails to communicate with Amazon Bedrock within 30 seconds, THEN THE FastAPI_Backend SHALL return an HTTP 503 response containing an error message indicating the AI service is temporarily unavailable, without exposing internal error details such as stack traces or service endpoints
2. IF the OMDb_Tool fails to retrieve data, THEN THE Bedrock_Client SHALL inform the user that movie data could not be retrieved and suggest trying again
3. IF an unexpected error occurs during request processing, THEN THE FastAPI_Backend SHALL log the error details including timestamp and error type to the application log, and return an HTTP 500 response containing a generic error message that does not expose internal system details
4. THE FastAPI_Backend SHALL ensure that no error response includes internal implementation details such as stack traces, file paths, or third-party service credentials
