"""Timeline + Summary routes — reads from InMemoryEventRepository and JobRepository."""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_event_repo, get_job_repo, get_video_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def timeline_root():
    return {"detail": "Provide a video_id: GET /timeline/{video_id}"}


@router.get("/{video_id}")
async def get_timeline(video_id: str):
    video_repo = get_video_repo()
    event_repo = get_event_repo()
    job_repo = get_job_repo()

    video = await video_repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    events = await event_repo.list_by_video(video_id)
    jobs = await job_repo.get_by_video(video_id)
    latest_job = jobs[0] if jobs else None

    return {
        "video_id":    video_id,
        "filename":    video.get("filename"),
        "metadata":    video.get("metadata", {}),
        "job_status":  latest_job["status"] if latest_job else None,
        "job_id":      latest_job["id"] if latest_job else None,
        "events":      events,
        "event_count": len(events),
    }
