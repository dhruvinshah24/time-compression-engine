"""Summary route — reads from InMemoryJobRepository."""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_job_repo, get_video_repo, get_event_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def summary_root():
    return {"detail": "Provide a video_id: GET /summary/{video_id}"}


@router.get("/{video_id}")
async def get_summary(video_id: str):
    video_repo = get_video_repo()
    job_repo = get_job_repo()
    event_repo = get_event_repo()

    video = await video_repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    jobs = await job_repo.get_by_video(video_id)
    latest_job = jobs[0] if jobs else None

    events = await event_repo.list_by_video(video_id)

    if not latest_job or latest_job["status"] != "completed":
        return {
            "video_id":    video_id,
            "status":      latest_job["status"] if latest_job else "not_started",
            "summary":     None,
            "events":      [],
            "stats":       {},
        }

    return {
        "video_id":    video_id,
        "status":      "completed",
        "filename":    video.get("filename"),
        "metadata":    video.get("metadata", {}),
        "summary":     latest_job.get("summary", {}),
        "export_manifest": latest_job.get("export_manifest", {}),
        "events":      events,
        "stats": {
            "event_count":       len(events),
            "total_duration_ms": latest_job.get("total_duration_ms"),
            "stages_completed":  len([s for s in latest_job.get("stages", []) if s["status"] == "success"]),
        },
    }
