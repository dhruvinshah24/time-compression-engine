"""Events route — reads from InMemoryEventRepository.

v1.0.1 additions:
  - GET /events/{event_id}/thumbnail — serves actual annotated thumbnail
  - GET /events/{event_id}/clip — serves actual event clip video
  - GET /events/{event_id}/preview — returns before/event/after frame paths
  - GET /events/{event_id}/evidence — full evidence chain with quality metadata
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.repositories.inmemory import get_event_repo

router = APIRouter()
logger = logging.getLogger(__name__)

# Allowed MIME types for clips
_VIDEO_MIME = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
}
# Allowed MIME types for images
_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


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


@router.get("/{event_id}/thumbnail")
async def get_event_thumbnail(event_id: str):
    """
    Serve the annotated thumbnail image for an event.

    Returns the actual JPEG image file.
    Returns 404 if no thumbnail was generated for this event.
    Never substitutes a placeholder image.
    """
    repo = get_event_repo()
    event = await repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    evidence = event.get("evidence") or {}
    thumb_path = evidence.get("thumbnail_path")

    if not thumb_path:
        raise HTTPException(
            status_code=404,
            detail=f"No thumbnail generated for event {event_id}. "
                   f"Run pipeline with frame_annotator enabled."
        )

    thumb_file = Path(thumb_path)
    if not thumb_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Thumbnail file missing from disk: {thumb_path}"
        )

    suffix = thumb_file.suffix.lower()
    media_type = _IMAGE_MIME.get(suffix, "image/jpeg")
    return FileResponse(
        path=str(thumb_file),
        media_type=media_type,
        filename=f"event_{event_id}_thumb{suffix}",
    )


@router.get("/{event_id}/frame/{frame_type}")
async def get_event_frame(event_id: str, frame_type: str):
    """
    Serve before / event / after frame images.

    frame_type: "before" | "event" | "after"

    Returns 404 if frame not generated.
    Never serves placeholder images.
    """
    if frame_type not in ("before", "event", "after"):
        raise HTTPException(
            status_code=400,
            detail=f"frame_type must be 'before', 'event', or 'after'. Got: {frame_type!r}"
        )

    repo = get_event_repo()
    event = await repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    evidence = event.get("evidence") or {}
    key_map = {
        "before": "before_frame_path",
        "event":  "event_frame_path",
        "after":  "after_frame_path",
    }
    path_key = key_map[frame_type]
    frame_path = evidence.get(path_key) or evidence.get("thumbnail_path")  # fallback for 'event'

    if not frame_path:
        raise HTTPException(
            status_code=404,
            detail=f"No {frame_type} frame generated for event {event_id}."
        )

    frame_file = Path(frame_path)
    if not frame_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"{frame_type.capitalize()} frame missing from disk: {frame_path}"
        )

    suffix = frame_file.suffix.lower()
    media_type = _IMAGE_MIME.get(suffix, "image/jpeg")
    return FileResponse(
        path=str(frame_file),
        media_type=media_type,
        filename=f"event_{event_id}_{frame_type}{suffix}",
    )


@router.get("/{event_id}/preview")
async def get_event_preview(event_id: str):
    """
    Return the before/event/after frame paths for the event preview modal.

    The frontend uses this to display:
      [ BEFORE FRAME ] [ EVENT FRAME ] [ AFTER FRAME ]
    """
    repo = get_event_repo()
    event = await repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    evidence = event.get("evidence") or {}

    def _path_or_none(key: str) -> str | None:
        p = evidence.get(key)
        if p and Path(p).exists():
            return p
        return None

    before_path = _path_or_none("before_frame_path")
    event_path  = _path_or_none("event_frame_path") or _path_or_none("thumbnail_path")
    after_path  = _path_or_none("after_frame_path")

    # Return API endpoint URLs — the actual FileResponse endpoints serve the files
    # regardless of where on disk they are stored.
    def _to_api_url(path: str | None) -> str | None:
        """Return a static URL if file is in /outputs, else None (use API endpoints instead)."""
        if not path:
            return None
        try:
            p = Path(path)
            parts = p.parts
            for i, part in enumerate(parts):
                if part == "outputs":
                    rel = "/".join(parts[i + 1:])
                    return f"/outputs/{rel}"
        except Exception:
            pass
        return None  # Caller should use /api/v1/events/{id}/thumbnail instead

    return {
        "event_id": event_id,
        "event_type": event.get("event_type"),
        "event_time_ms": event.get("start_ms"),
        "confidence": event.get("confidence"),
        "track_id": event.get("track_id"),
        "person_label": evidence.get("person_label"),
        "frames": {
            "before": {
                "path": before_path,
                "url": f"/api/v1/events/{event_id}/frame/before" if before_path else None,
                "available": before_path is not None,
            },
            "event": {
                "path": event_path,
                "url": f"/api/v1/events/{event_id}/frame/event" if event_path else None,
                "available": event_path is not None,
            },
            "after": {
                "path": after_path,
                "url": f"/api/v1/events/{event_id}/frame/after" if after_path else None,
                "available": after_path is not None,
            },
        },
        # Canonical API URLs — always work regardless of storage location
        "thumbnail_url": f"/api/v1/events/{event_id}/thumbnail" if evidence.get("thumbnail_path") else None,
        "clip_url": f"/api/v1/events/{event_id}/clip" if evidence.get("clip_path") else None,
        "evidence": {
            "lighting_condition": evidence.get("lighting_condition", "unknown"),
            "preprocessing_mode": evidence.get("preprocessing_mode", "off"),
            "zone_id": evidence.get("zone_id"),
            "direction": evidence.get("direction"),
            "description": evidence.get("description"),
        },
    }


@router.get("/{event_id}/clip")
async def get_event_clip(event_id: str):
    """
    Serve the generated event clip video.

    Returns the actual video file.
    Returns 404 with a meaningful error if clip was not generated.
    Never returns fake media.
    """
    repo = get_event_repo()
    event = await repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    evidence = event.get("evidence") or {}
    clip_path = evidence.get("clip_path")

    if not clip_path:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No clip generated for event {event_id}. "
                "Clip generation requires ffmpeg to be installed and the pipeline "
                "to have run with clip generation enabled."
            )
        )

    clip_file = Path(clip_path)
    if not clip_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Clip file missing from disk: {clip_path}. "
                   f"FFmpeg may have failed during generation."
        )

    if clip_file.stat().st_size == 0:
        raise HTTPException(
            status_code=422,
            detail=f"Clip file exists but is empty: {clip_path}. "
                   f"FFmpeg generation likely failed — check pipeline logs."
        )

    suffix = clip_file.suffix.lower()
    media_type = _VIDEO_MIME.get(suffix, "video/mp4")
    return FileResponse(
        path=str(clip_file),
        media_type=media_type,
        filename=f"event_{event_id}_clip{suffix}",
    )


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


@router.get("/{event_id}/evidence")
async def get_event_evidence(event_id: str):
    """
    Full evidence chain for an event.

    Returns:
      WHAT: event_type
      WHEN: start_ms / end_ms
      WHERE: centroid_x/y, zone_id
      TRACK: track_id, person_label
      CONFIDENCE: confidence + per-evidence confidence
      WHY: description, rule_name
      EVIDENCE: full evidence dict with all signals
    """
    repo = get_event_repo()
    event = await repo.get(event_id)
    if not event:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    evidence = event.get("evidence") or {}

    return {
        "event_id": event_id,
        "what": event.get("event_type"),
        "when": {
            "start_ms": event.get("start_ms"),
            "end_ms": event.get("end_ms"),
            "start_formatted": _format_ms(event.get("start_ms", 0)),
            "end_formatted": _format_ms(event.get("end_ms", 0)),
        },
        "where": {
            "centroid_x": evidence.get("centroid_x"),
            "centroid_y": evidence.get("centroid_y"),
            "zone_id": evidence.get("zone_id"),
            "zone_name": evidence.get("zone_name"),
            "direction": evidence.get("direction"),
        },
        "track": {
            "track_id": event.get("track_id"),
            "person_label": evidence.get("person_label"),
            "crop_path": evidence.get("crop_path"),
        },
        "confidence": {
            "overall": event.get("confidence"),
            "track_confidence": evidence.get("track_confidence"),
            "roi_confidence": evidence.get("roi_confidence"),
            "scene_quality": evidence.get("scene_quality_score"),
        },
        "why": {
            "rule_name": event.get("rule_name"),
            "description": evidence.get("description"),
            "dependencies": event.get("dependencies", []),
        },
        "evidence": evidence,
        "media": {
            "thumbnail_path": evidence.get("thumbnail_path"),
            "before_frame_path": evidence.get("before_frame_path"),
            "event_frame_path": evidence.get("event_frame_path"),
            "after_frame_path": evidence.get("after_frame_path"),
            "clip_path": evidence.get("clip_path"),
        },
        "quality": {
            "lighting_condition": evidence.get("lighting_condition", "unknown"),
            "preprocessing_mode": evidence.get("preprocessing_mode", "off"),
        },
    }


def _format_ms(ms: float | None) -> str:
    """Format milliseconds as MM:SS.mmm"""
    if ms is None:
        return "00:00.000"
    total_s = ms / 1000.0
    minutes = int(total_s // 60)
    seconds = total_s % 60
    return f"{minutes:02d}:{seconds:06.3f}"
