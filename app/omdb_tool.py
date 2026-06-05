"""
OMDb Tool for CineAgent.

Queries the OMDb API to retrieve movie and TV series information.
Handles input validation, HTTP errors, and timeouts gracefully.
"""

import httpx

from app.models import OMDbResult

# OMDb API base URL
OMDB_API_URL = "http://www.omdbapi.com/"


class OMDbTool:
    """Queries the OMDb API by title and returns structured results.

    Attributes:
        api_key: The OMDb API key for authentication.
        timeout: Maximum seconds to wait for an API response (default 10s).
    """

    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self.api_key = api_key
        self.timeout = timeout

    async def search_by_title(self, title: str) -> OMDbResult:
        """Search OMDb API by title.

        Validates the title, queries the API, and returns a structured result.
        Returns an error OMDbResult without making an HTTP call if the title
        is empty or whitespace-only.

        Args:
            title: The movie or series title to search for.

        Returns:
            OMDbResult with success=True and metadata on match, or
            success=False with an error message on failure.
        """
        # Validate title is not empty or whitespace-only
        if not title or not title.strip():
            return OMDbResult(
                success=False,
                error="A non-empty title is required.",
            )

        # Query OMDb API
        params = {"t": title.strip(), "apikey": self.api_key}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(OMDB_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            return OMDbResult(
                success=False,
                error="OMDb API request timed out.",
            )
        except httpx.HTTPStatusError as exc:
            return OMDbResult(
                success=False,
                error=f"OMDb API HTTP error: {exc.response.status_code}",
            )
        except httpx.HTTPError as exc:
            return OMDbResult(
                success=False,
                error=f"OMDb API request failed: {exc}",
            )

        # Check if OMDb found a match
        if data.get("Response") == "False":
            return OMDbResult(
                success=False,
                error=data.get("Error", "No matching title found."),
            )

        # Extract metadata from successful response
        content_type = data.get("Type", "movie")
        total_seasons = data.get("totalSeasons") if content_type == "series" else None
        poster = data.get("Poster")
        # OMDb returns "N/A" when no poster is available
        if poster == "N/A":
            poster = None

        return OMDbResult(
            success=True,
            title=data.get("Title"),
            year=data.get("Year"),
            plot=data.get("Plot"),
            genre=data.get("Genre"),
            ratings=data.get("Ratings"),
            content_type=content_type,
            total_seasons=total_seasons,
            poster=poster,
        )
