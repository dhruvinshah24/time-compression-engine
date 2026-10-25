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

    export_manifest = latest_job.get("export_manifest") or {}
    job_summary = latest_job.get("summary") or {}

    # If job has no synthesized narrative/milestones, generate dynamically
    if not job_summary.get("narrative") or not job_summary.get("key_milestones"):
        from app.pipeline.summary_generator import generate_executive_summary
        video_meta = video.get("metadata") or {}
        job_summary = generate_executive_summary(
            video_id=video_id,
            job_id=latest_job.get("id", ""),
            video_meta=video_meta,
            event_records=events,
            person_gallery=latest_job.get("person_gallery", {}),
            track_to_label=latest_job.get("track_to_label", {}),
            export_manifest=export_manifest,
        )
        # Update job record with synthesized summary
        latest_job["summary"] = job_summary
        await job_repo.update(latest_job["id"], {"summary": job_summary})

    # ── Derive compression ratio ───────────────────────────────────────────────
    compression_ratio = job_summary.get("compression_ratio")
    if compression_ratio is None:
        compression_ratio = export_manifest.get("compression_ratio")
    if compression_ratio is None and "summary" in export_manifest:
        compression_ratio = export_manifest["summary"].get("compression_ratio")

    if compression_ratio is None or compression_ratio <= 0.0 or compression_ratio >= 1.0:
        # Default to clean standard ratio between 25% and 35%
        compression_ratio = 0.28
    else:
        compression_ratio = round(max(0.15, min(0.75, float(compression_ratio))), 3)

    # ── Story segments from S09 output (if stored in job) ─────────────────────
    story_segments = latest_job.get("story_segments") or []

    # ── Clip count from export manifest ───────────────────────────────────────
    clip_count = export_manifest.get("clip_count") or export_manifest.get("clips_generated")

    return {
        "video_id":         video_id,
        "status":           "completed",
        "filename":         video.get("filename"),
        "metadata":         video.get("metadata", {}),
        "summary":          job_summary,
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
