"""Videos route — reads from InMemoryVideoRepository."""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_video_repo, get_job_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def list_videos():
    repo = get_video_repo()
    videos = await repo.list()
    # Enrich with latest job status
    job_repo = get_job_repo()
    result = []
    for v in videos:
        jobs = await job_repo.get_by_video(v["id"])
        latest_job = jobs[0] if jobs else None
        result.append({
            **v,
            "latest_job_status": latest_job["status"] if latest_job else None,
            "latest_job_id": latest_job["id"] if latest_job else None,
        })
    return result


@router.get("/{video_id}")
async def get_video(video_id: str):
    repo = get_video_repo()
    video = await repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return video


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    repo = get_video_repo()
    deleted = await repo.delete(video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return {"status": "deleted", "video_id": video_id}
