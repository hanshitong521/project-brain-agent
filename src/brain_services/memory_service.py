from __future__ import annotations

import os
import uuid
from typing import Any

from mem0 import Memory

COLLECTION_MEMORY = "memory_experience"


class MemoryService:
    """Mem0-backed experience memory (collection isolated via config)."""

    def __init__(self, qdrant_url: str | None = None) -> None:
        url = qdrant_url or os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
        self._use_local_fallback = os.environ.get("BRAIN_QDRANT_MODE") == "memory"
        config: dict[str, Any] = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": COLLECTION_MEMORY,
                    "embedding_model_dims": 1536,
                },
            }
        }
        if self._use_local_fallback:
            config["vector_store"]["config"] = {
                "collection_name": COLLECTION_MEMORY,
                "path": os.environ.get(
                    "BRAIN_QDRANT_PATH",
                    os.path.join(os.path.dirname(__file__), "..", "..", ".data", "qdrant"),
                ),
            }
            config["vector_store"]["provider"] = "qdrant"
            # qdrant local path mode
            config["vector_store"]["config"]["on_disk"] = True
        else:
            config["vector_store"]["config"]["url"] = url

        self._memory = Memory.from_config(config)

    def search(self, project_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
        limit = min(limit, 5)
        user_id = f"project:{project_id}"
        results = self._memory.search(query=query, user_id=user_id, limit=limit)
        if isinstance(results, dict):
            return results.get("results") or results.get("memories") or []
        return list(results) if results else []

    def add(
        self,
        project_id: str,
        summary: str,
        importance: str = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        user_id = f"project:{project_id}"
        meta = {"importance": importance, **(metadata or {})}
        out = self._memory.add(summary, user_id=user_id, metadata=meta)
        if isinstance(out, dict) and out.get("id"):
            return str(out["id"])
        return str(uuid.uuid4())
