"""
In-memory repository implementations — Time Compression Engine v1.0.1.

These implement the same interfaces as the PostgreSQL repositories but store
data in process memory. They are the active implementations until PostgreSQL
is wired in v1.1.

Thread-safety: asyncio.Lock used for all mutations. All data is stored as
plain dicts (not SQLAlchemy models) so this layer has zero DB dependency.

Migration path to PostgreSQL:
- Replace `get_video_repo()` / `get_job_repo()` / `get_event_repo()` in
  app/api/v1/router.py to return the Postgres implementations.
- The routes themselves require no changes.
"""

from __future__ import annotations
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Video Repository
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryVideoRepository:
    """Stores video records in a process-level dict."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: dict) -> dict:
        async with self._lock:
            self._store[record["id"]] = {**record, "created_at": _utcnow()}
            logger.debug("VideoRepo.create: %s", record["id"])
            return self._store[record["id"]]

    async def get(self, video_id: str) -> dict | None:
        return self._store.get(video_id)

    async def list(self) -> list[dict]:
        return list(self._store.values())

    async def delete(self, video_id: str) -> bool:
        async with self._lock:
            return self._store.pop(video_id, None) is not None


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Job Repository
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryJobRepository:
    """Stores processing job records in a process-level dict."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: dict) -> dict:
        async with self._lock:
            self._store[record["id"]] = {**record, "created_at": _utcnow()}
            logger.debug("JobRepo.create: %s", record["id"])
            return self._store[record["id"]]

    async def get(self, job_id: str) -> dict | None:
        return self._store.get(job_id)

    async def list(self) -> list[dict]:
        # Newest first
        return sorted(self._store.values(), key=lambda r: r.get("created_at", ""), reverse=True)

    async def update(self, job_id: str, fields: dict) -> dict | None:
        async with self._lock:
            if job_id not in self._store:
                return None
            self._store[job_id].update(fields)
            self._store[job_id]["updated_at"] = _utcnow()
            return self._store[job_id]

    async def get_by_video(self, video_id: str) -> list[dict]:
        return [r for r in self._store.values() if r.get("video_id") == video_id]


# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Event Repository
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryEventRepository:
    """Stores detected events in a process-level dict."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def create_many(self, records: list[dict]) -> list[dict]:
        async with self._lock:
            created = []
            for r in records:
                self._store[r["id"]] = {**r, "created_at": _utcnow()}
                created.append(self._store[r["id"]])
            logger.debug("EventRepo.create_many: %d events", len(created))
            return created

    async def list_by_video(self, video_id: str) -> list[dict]:
        return sorted(
            [r for r in self._store.values() if r.get("video_id") == video_id],
            key=lambda r: r.get("timestamp_ms", 0),
        )

    async def list_all(self) -> list[dict]:
        return sorted(self._store.values(), key=lambda r: r.get("created_at", ""), reverse=True)

    async def get(self, event_id: str) -> dict | None:
        return self._store.get(event_id)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton store — one instance shared across all requests
# ─────────────────────────────────────────────────────────────────────────────

_video_repo: InMemoryVideoRepository | None = None
_job_repo: InMemoryJobRepository | None = None
_event_repo: InMemoryEventRepository | None = None


def get_video_repo() -> InMemoryVideoRepository:
    global _video_repo
    if _video_repo is None:
        _video_repo = InMemoryVideoRepository()
    return _video_repo


def get_job_repo() -> InMemoryJobRepository:
    global _job_repo
    if _job_repo is None:
        _job_repo = InMemoryJobRepository()
    return _job_repo


def get_event_repo() -> InMemoryEventRepository:
    global _event_repo
    if _event_repo is None:
        _event_repo = InMemoryEventRepository()
    return _event_repo
