"""
Simple JSON file-based data layer for CineAgent.

Stores conversation history locally so users can see past conversations
in the Chainlit sidebar. Simple and didactic for the workshop.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from chainlit.data import BaseDataLayer
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser

logger = logging.getLogger(__name__)

# Directory to store conversation data
DATA_DIR = Path(os.environ.get("CINEAGENT_DATA_DIR", ".data"))


class JSONDataLayer(BaseDataLayer):
    """A simple JSON file-based data layer for local development."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.threads_dir = DATA_DIR / "threads"
        self.threads_dir.mkdir(parents=True, exist_ok=True)

    def _thread_path(self, thread_id: str) -> Path:
        return self.threads_dir / f"{thread_id}.json"

    def _load_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        path = self._thread_path(thread_id)
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None

    def _save_thread(self, thread_id: str, data: Dict[str, Any]) -> None:
        path = self._thread_path(thread_id)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    # --- User methods ---

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        return PersistedUser(
            id=identifier,
            identifier=identifier,
            metadata={},
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

    async def create_user(self, user: Any) -> Optional[PersistedUser]:
        identifier = getattr(user, "identifier", "anonymous")
        return PersistedUser(
            id=identifier,
            identifier=identifier,
            metadata={},
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

    # --- Thread methods ---

    async def get_thread_author(self, thread_id: str) -> str:
        thread = self._load_thread(thread_id)
        if thread:
            return thread.get("user_id", "anonymous")
        return "anonymous"

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        thread = self._load_thread(thread_id)
        if not thread:
            return None
        return ThreadDict(
            id=thread["id"],
            name=thread.get("name", "Conversation"),
            createdAt=thread.get("created_at", datetime.now(timezone.utc).isoformat()),
            userId=thread.get("user_id", "anonymous"),
            userIdentifier=thread.get("user_id", "anonymous"),
            steps=thread.get("steps", []),
            metadata=thread.get("metadata", {}),
            tags=thread.get("tags", []),
        )

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        thread = self._load_thread(thread_id)
        if thread is None:
            thread = {
                "id": thread_id,
                "name": name or "New Conversation",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id or "anonymous",
                "steps": [],
                "metadata": metadata or {},
                "tags": tags or [],
            }
        else:
            if name is not None:
                thread["name"] = name
            if user_id is not None:
                thread["user_id"] = user_id
            if metadata is not None:
                thread["metadata"] = metadata
            if tags is not None:
                thread["tags"] = tags
        self._save_thread(thread_id, thread)

    async def delete_thread(self, thread_id: str) -> None:
        path = self._thread_path(thread_id)
        if path.exists():
            path.unlink()

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        all_threads: List[ThreadDict] = []

        for file in self.threads_dir.glob("*.json"):
            try:
                with open(file, "r") as f:
                    data = json.load(f)
                if filters.userId and data.get("user_id") != filters.userId:
                    continue
                all_threads.append(
                    ThreadDict(
                        id=data["id"],
                        name=data.get("name", "Conversation"),
                        createdAt=data.get("created_at", ""),
                        userId=data.get("user_id", "anonymous"),
                        userIdentifier=data.get("user_id", "anonymous"),
                        steps=data.get("steps", []),
                        metadata=data.get("metadata", {}),
                        tags=data.get("tags", []),
                    )
                )
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort newest first
        all_threads.sort(key=lambda t: t.get("createdAt", ""), reverse=True)

        # Pagination
        first = pagination.first or 20
        cursor_idx = 0
        if pagination.cursor:
            for i, t in enumerate(all_threads):
                if t["id"] == pagination.cursor:
                    cursor_idx = i + 1
                    break

        page = all_threads[cursor_idx : cursor_idx + first]

        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=cursor_idx + first < len(all_threads),
                startCursor=page[0]["id"] if page else None,
                endCursor=page[-1]["id"] if page else None,
            ),
            data=page,
        )

    # --- Step methods ---

    async def create_step(self, step_dict: Any) -> None:
        # step_dict might be a StepDict TypedDict or dict
        if hasattr(step_dict, "get"):
            thread_id = step_dict.get("threadId")
        else:
            thread_id = getattr(step_dict, "threadId", None)

        if not thread_id:
            return

        thread = self._load_thread(thread_id)
        if thread is None:
            thread = {
                "id": thread_id,
                "name": "New Conversation",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "user_id": "anonymous",
                "steps": [],
                "metadata": {},
                "tags": [],
            }

        # Convert to dict if needed
        step_data = dict(step_dict) if hasattr(step_dict, "get") else step_dict
        thread["steps"].append(step_data)

        # Auto-name from first user message
        if thread["name"] == "New Conversation":
            step_type = step_data.get("type", "")
            output = step_data.get("output", "") or ""
            input_text = step_data.get("input", "") or ""
            msg = input_text or output
            if msg and step_type == "user_message":
                thread["name"] = msg[:50] + ("..." if len(msg) > 50 else "")

        self._save_thread(thread_id, thread)

    async def update_step(self, step_dict: Any) -> None:
        if hasattr(step_dict, "get"):
            thread_id = step_dict.get("threadId")
            step_id = step_dict.get("id")
        else:
            thread_id = getattr(step_dict, "threadId", None)
            step_id = getattr(step_dict, "id", None)

        if not thread_id:
            return

        thread = self._load_thread(thread_id)
        if thread is None:
            await self.create_step(step_dict)
            return

        step_data = dict(step_dict) if hasattr(step_dict, "get") else step_dict
        for i, existing in enumerate(thread.get("steps", [])):
            if existing.get("id") == step_id:
                thread["steps"][i] = step_data
                self._save_thread(thread_id, thread)
                return

        thread["steps"].append(step_data)
        self._save_thread(thread_id, thread)

    async def delete_step(self, step_id: str) -> None:
        pass

    # --- Element methods ---

    async def get_element(self, thread_id: str, element_id: str) -> Optional[Any]:
        return None

    async def create_element(self, element: Any) -> None:
        pass

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None) -> None:
        pass

    # --- Feedback methods ---

    async def upsert_feedback(self, feedback: Feedback) -> str:
        return ""

    async def delete_feedback(self, feedback_id: str) -> bool:
        return True

    # --- Favorites ---

    async def get_favorite_steps(self, user_id: str) -> List[Any]:
        return []

    async def set_step_favorite(self, step_dict: Any, favorite: bool) -> Any:
        return step_dict

    # --- Misc ---

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        pass
