"""Timeline route — returns events + detected objects + person gallery + categorized sections.

Fix log:
  v1.1: Extended _categorize() to handle all Pass 6 interaction event types
  v1.2: Added person_gallery, persons, crop_url to response (Phase 7 ReID)
  v1.2: Added narrative event types (cycling, walking_upstairs, etc.)
  v1.2: Added /crops/{job_id}/{filename} static file serving for person thumbnails
"""
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.repositories.inmemory import get_event_repo, get_job_repo, get_video_repo

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Event category mapping ─────────────────────────────────────────────────────
_ACTIVITY_TYPES = {
    "person_entered_scene", "person_left_scene", "person_walking",
    "person_running", "person_standing", "person_sitting",
    "person_standing_up", "person_loitering", "person_reaching_up",
    # Phase 7 narrative types
    "walking", "running", "loitering", "entering_scene",
}
_LIGHTING_TYPES = {"light_turned_on", "light_turned_off"}

_INTERACTION_TYPES = {
    "person_using_phone", "person_using_laptop", "person_drinking",
    "person_reading", "person_watching_screen", "person_pocketed_object",
    "person_at_desk", "person_near_screen",
}

# Phase 7: activity types from ActivityClassifier
_ACTIVITY_CLASSIFIER_TYPES = {
    "cycling", "walking_upstairs", "walking_downstairs",
}


def _categorize(event_type: str) -> str:
    """Map event_type string to timeline category."""
    if event_type in _ACTIVITY_TYPES or event_type in _ACTIVITY_CLASSIFIER_TYPES:
        return "activity"
    if event_type in _LIGHTING_TYPES:
        return "lighting"
    if event_type in _INTERACTION_TYPES:
        return "interaction"
    # Dynamic interaction types
    if (event_type.startswith("person_picked_up_")
            or event_type.startswith("person_placed_")
            or event_type.startswith("person_pocketed_")):
        return "interaction"
    if event_type.startswith("person_near_"):
        return "interaction"
    if event_type.startswith("vehicle_"):
        return "vehicle"
    return "other"


def _make_crop_url(crop_path: str | None, job_id: str) -> str | None:
    """Convert absolute crop path to a frontend-accessible full URL."""
    if not crop_path:
        return None
    try:
        p = Path(crop_path)
        # Return full URL so the frontend doesn't double-prefix it
        return f"http://localhost:8000/api/v1/timeline/crops/{job_id}/{p.name}"
    except Exception:
        return None


def _enrich_event(evt: dict, job_id: str) -> dict:
    """Add frontend-friendly fields to an event dict."""
    evidence = evt.get("evidence") or {}

    # Person label from evidence
    person_label = evidence.get("person_label")
    crop_path    = evidence.get("crop_path")
    description  = evidence.get("description")

    # Prefer narrative description over raw event_type
    display_name = description or evt.get("event_type", "")

    return {
        **evt,
        "person_label": person_label,
        "crop_url":     _make_crop_url(crop_path, job_id or ""),
        "display_name": display_name,
        "direction":    evidence.get("direction") or evidence.get("entry_direction"),
    }


@router.get("/")
async def timeline_root():
    return {"detail": "Provide a video_id: GET /timeline/{video_id}"}


@router.get("/crops/{job_id}/{filename}")
async def serve_crop(job_id: str, filename: str):
    """Serve person crop thumbnails for the frontend."""
    from app.core.config import settings as app_settings
    crops_dir = Path(app_settings.OUTPUT_DIR) / job_id / "crops"
    file_path = crops_dir / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Crop not found: {filename}")

    return FileResponse(
        path=str(file_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/{video_id}")
async def get_timeline(video_id: str):
    video_repo = get_video_repo()
    event_repo = get_event_repo()
    job_repo   = get_job_repo()

    video = await video_repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    events  = await event_repo.list_by_video(video_id)
    jobs    = await job_repo.get_by_video(video_id)

    jobs_sorted = sorted(
        jobs,
        key=lambda j: (0 if j.get("status") == "completed" else 1, j.get("created_at", "")),
    )
    latest_job = jobs_sorted[0] if jobs_sorted else None
    job_id = latest_job["id"] if latest_job else ""

    # ── Enrich events with person labels and crop URLs ────────────────────────
    enriched_events = [_enrich_event(evt, job_id) for evt in events]

    # ── Categorize enriched events ────────────────────────────────────────────
    events_by_category: dict[str, list] = {
        "activity": [], "lighting": [], "interaction": [],
        "vehicle": [], "other": [],
    }
    for evt in enriched_events:
        cat = _categorize(evt.get("event_type") or evt.get("type") or "")
        events_by_category[cat].append(evt)

    # ── Pull detected objects from job record ─────────────────────────────────
    detected_objects = []
    if latest_job:
        detected_objects = latest_job.get("detected_objects", [])

    # ── Person gallery ────────────────────────────────────────────────────────
    # Built by s05 ReID pass, stored in job record under "person_gallery"
    person_gallery: dict = {}
    if latest_job:
        person_gallery = latest_job.get("person_gallery") or {}

    # Build persons list for UI — one entry per unique "Person N"
    persons: list[dict] = []
    for label, entry in sorted(person_gallery.items()):
        persons.append({
            "person_label":      label,
            "first_seen_ms":     entry.get("first_seen_ms", 0),
            "last_seen_ms":      entry.get("last_seen_ms", 0),
            "observation_count": entry.get("observation_count", 0),
            "entry_direction":   entry.get("entry_direction"),
            "crop_url":          _make_crop_url(entry.get("best_crop_path"), job_id),
            "track_ids":         entry.get("track_ids", []),
        })

    # ── Video metadata ─────────────────────────────────────────────────────────
    video_meta = video.get("metadata") or {}
    if latest_job and not video_meta:
        video_meta = latest_job.get("video_metadata") or {}

    duration_seconds = (
        video_meta.get("duration_seconds")
        or video_meta.get("duration_s")
        or (video.get("duration_seconds") if isinstance(video, dict) else None)
        or 0
    )

    category_counts   = {k: len(v) for k, v in events_by_category.items()}
    total_meaningful  = sum(len(v) for k, v in events_by_category.items() if k != "other")

    return {
        "video_id":           video_id,
        "filename":           video.get("filename"),
        "metadata":           video_meta,
        "duration_seconds":   duration_seconds,
        "job_status":         latest_job["status"] if latest_job else None,
        "job_id":             job_id,
        "detected_objects":   detected_objects,
        "events":             enriched_events,
        "event_count":        len(enriched_events),
        "meaningful_events":  total_meaningful,
        "events_by_category": category_counts,
        "activity_events":    events_by_category["activity"],
        "lighting_events":    events_by_category["lighting"],
        "interaction_events": events_by_category["interaction"],
        "vehicle_events":     events_by_category["vehicle"],
        # Phase 7: Person identity data
        "persons":            persons,
        "person_gallery":     person_gallery,
        "unique_persons":     len(persons),
    }
