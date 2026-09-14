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

    # ── Derive compression ratio ───────────────────────────────────────────────
    # Try from export_manifest first, then derive from job metrics
    export_manifest = latest_job.get("export_manifest") or {}
    compression_ratio = export_manifest.get("compression_ratio")

    if compression_ratio is None:
        # Try from job-level metrics written by S10/S11
        for stage in latest_job.get("stages", []):
            metrics = stage.get("metrics") or {}
            if "compression_ratio" in metrics:
                compression_ratio = metrics["compression_ratio"]
                break

    if compression_ratio is None:
        # Derive from total_duration_ms vs original video duration
        video_meta = video.get("metadata") or {}
        original_duration_s = video_meta.get("duration_seconds")
        total_duration_ms = latest_job.get("total_duration_ms")
        if original_duration_s and total_duration_ms:
            retained_s = total_duration_ms / 1000.0
            original_s = original_duration_s
            if original_s > 0:
                compression_ratio = round(retained_s / original_s, 3)

    # ── Story segments from S09 output (if stored in job) ─────────────────────
    story_segments = latest_job.get("story_segments") or []

    # ── Clip count from export manifest ───────────────────────────────────────
    clip_count = export_manifest.get("clip_count") or export_manifest.get("clips_generated")

    return {
        "video_id":         video_id,
        "status":           "completed",
        "filename":         video.get("filename"),
        "metadata":         video.get("metadata", {}),
        "summary":          latest_job.get("summary", {}),
        "export_manifest":  export_manifest,
        "story_segments":   story_segments,
        "events":           events,
        "stats": {
            "event_count":       len(events),
            "total_duration_ms": latest_job.get("total_duration_ms"),
            "stages_completed":  len([s for s in latest_job.get("stages", []) if s["status"] == "success"]),
            "compression_ratio": compression_ratio,
            "clip_count":        clip_count,
            "story_count":       len(story_segments),
        },
    }
