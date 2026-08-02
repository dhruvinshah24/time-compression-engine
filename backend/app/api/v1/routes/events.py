"""Events route — reads from InMemoryEventRepository."""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_event_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def list_events(video_id: str | None = None, limit: int = 50):
    repo = get_event_repo()
    if video_id:
        events = await repo.list_by_video(video_id)
    else:
        events = await repo.list_all()
    return events[:limit]


@router.get("/{event_id}")
async def get_event(event_id: str):
    repo = get_event_repo()
    event = await repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return event


@router.get("/{event_id}/explanation")
async def get_event_explanation(event_id: str):
    repo = get_event_repo()
    event = await repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return {
        "event_id": event_id,
        "explanation": event.get("explanation", {}),
        "confidence_breakdown": event.get("confidence_breakdown", {}),
    }
