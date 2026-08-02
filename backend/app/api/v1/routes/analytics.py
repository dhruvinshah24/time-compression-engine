"""Analytics route — computes real stats from InMemory repositories."""
import logging
from fastapi import APIRouter
from app.repositories.inmemory import get_job_repo, get_video_repo, get_event_repo

router = APIRouter()
logger = logging.getLogger(__name__)


async def _compute_stats() -> dict:
    videos = await get_video_repo().list()
    jobs = await get_job_repo().list()
    events = await get_event_repo().list_all()

    completed_jobs = [j for j in jobs if j["status"] == "completed"]
    failed_jobs    = [j for j in jobs if j["status"] == "failed"]
    running_jobs   = [j for j in jobs if j["status"] == "running"]

    # Compression ratios from completed jobs
    ratios = []
    for job in completed_jobs:
        meta = job.get("video_metadata", {})
        duration_s = meta.get("duration_seconds") or 0
        n_events = job.get("event_count", 0)
        if duration_s > 0 and n_events > 0:
            # Simple approximation: ratio of original duration to kept events duration
            # Will be replaced by real export_manifest data once pipeline runs
            ratios.append(round(duration_s / max(1, n_events), 1))

    avg_compression = round(sum(ratios) / len(ratios), 1) if ratios else 0.0

    # Storage saved estimate (very rough: original - thumbnails)
    total_bytes = sum(
        v.get("file_size_bytes", 0) for v in videos
    )

    # Stage timing data (for the analytics bar chart)
    stage_timing: dict[str, list[int]] = {}
    for job in completed_jobs:
        for stage in job.get("stages", []):
            key = stage["name"]
            ms = stage.get("duration_ms")
            if ms:
                stage_timing.setdefault(key, []).append(ms)

    stage_averages = [
        {"stage": k, "ms": round(sum(v) / len(v))}
        for k, v in stage_timing.items()
    ]

    return {
        "total_videos":         len(videos),
        "total_jobs":           len(jobs),
        "completed_jobs":       len(completed_jobs),
        "failed_jobs":          len(failed_jobs),
        "running_jobs":         len(running_jobs),
        "total_events":         len(events),
        "avg_compression_ratio": avg_compression,
        "total_bytes_uploaded": total_bytes,
        "stage_averages":       stage_averages,
        "has_data":             len(videos) > 0,
    }


@router.get("/")
async def get_analytics_summary():
    return await _compute_stats()


@router.get("/stats")
async def get_stats():
    return await _compute_stats()
