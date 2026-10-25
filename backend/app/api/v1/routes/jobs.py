"""Jobs route — reads from InMemoryJobRepository."""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_job_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
@router.get("/")
async def list_jobs():
    repo = get_job_repo()
    return await repo.list()


@router.get("/{job_id}")
async def get_job(job_id: str):
    repo = get_job_repo()
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    repo = get_job_repo()
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    updated = await repo.update(job_id, {"status": "cancelled"})
    return {"status": "cancelled", "job_id": job_id}


@router.post("/{job_id}/reprocess")
async def reprocess_job(job_id: str):
    """Re-run the pipeline for an existing job using latest models & filters."""
    import asyncio
    from pathlib import Path
    from app.pipeline.context import PipelineContext
    from app.pipeline.orchestrator import PipelineOrchestrator
    from app.repositories.inmemory import get_event_repo, get_video_repo

    job_repo = get_job_repo()
    job = await job_repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    video_repo = get_video_repo()
    event_repo = get_event_repo()
    video_id = job.get("video_id")
    video = await video_repo.get(video_id) if video_id else None

    # Find the video file path
    video_path = None
    if video and video.get("file_path"):
        video_path = video["file_path"]
    elif job.get("video_metadata", {}).get("file_path"):
        video_path = job["video_metadata"]["file_path"]

    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=400, detail="Original video file not found on disk.")

    # Clear old events for this video so stale events are removed
    if video_id:
        async with event_repo._lock:
            to_remove = [k for k, v in event_repo._store.items() if v.get("video_id") == video_id]
            for k in to_remove:
                event_repo._store.pop(k, None)

    output_dir = str(Path(video_path).parent)
    settings = dict(job.get("settings", {}))
    settings["detection_confidence"] = 0.25
    settings["require_bicycle_for_cycling"] = True
    settings["adaptive_skip"] = True

    context = PipelineContext(
        job_id=job_id,
        video_id=video_id,
        video_path=video_path,
        output_dir=output_dir,
        settings=settings,
    )

    orchestrator = PipelineOrchestrator(job_repo=job_repo, event_repo=event_repo)

    async def run_pipeline():
        try:
            await orchestrator.run(context)
        except Exception as exc:
            logger.exception("[%s] Reprocess failed", job_id)
            await job_repo.update(job_id, {
                "status": "failed",
                "error": f"Reprocess failed: {exc}",
            })

    asyncio.create_task(run_pipeline())
    return {"status": "reprocessing_started", "job_id": job_id, "video_id": video_id}
