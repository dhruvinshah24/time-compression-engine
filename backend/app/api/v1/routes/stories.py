"""
Stories route — GET /stories/{video_id}

Builds story arcs per person/track from events in the event repository.
No ML inference — pure read-only aggregation of already-detected events.

Story arc = all events attributed to the same person_label or track_id,
ordered chronologically, with derived metadata (duration, event count, etc.)
"""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_event_repo, get_job_repo, get_video_repo

router = APIRouter()
logger = logging.getLogger(__name__)


def _fmt_ms(ms: float | None) -> str:
    if ms is None:
        return "00:00"
    total_s = ms / 1000.0
    m = int(total_s // 60)
    s = int(total_s % 60)
    return f"{m:02d}:{s:02d}"


def _event_label(et: str) -> str:
    return et.replace("_", " ").title()


@router.get("/")
async def stories_root():
    return {"detail": "Provide a video_id: GET /stories/{video_id}"}


@router.get("/{video_id}")
async def get_stories(video_id: str):
    """
    Return story arcs for a video — one arc per identified person/track.

    Each arc contains:
      - story_id: unique identifier
      - person_label: e.g. "Person-A" or None
      - track_id: numeric track ID if available
      - events: list of events ordered by timestamp
      - start_ms / end_ms: temporal span of the arc
      - duration_ms: total duration of the story
      - event_count: total number of events
      - summary: human-readable description derived from events
      - entry_direction / exit_direction: if detectable from events
    """
    video_repo = get_video_repo()
    video = await video_repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    job_repo = get_job_repo()
    jobs = await job_repo.get_by_video(video_id)
    latest_job = jobs[0] if jobs else None
    if not latest_job or latest_job.get("status") != "completed":
        return {
            "video_id": video_id,
            "status": latest_job["status"] if latest_job else "not_started",
            "stories": [],
            "total_stories": 0,
        }

    event_repo = get_event_repo()
    events = await event_repo.list_by_video(video_id)

    if not events:
        return {
            "video_id": video_id,
            "status": "completed",
            "stories": [],
            "total_stories": 0,
        }

    # ── Group events by person_label, then track_id, then "global" ────────────
    arcs: dict[str, list[dict]] = {}

    for evt in events:
        evidence = evt.get("evidence") or {}
        person_label = evidence.get("person_label") or evt.get("person_label")
        track_id = evt.get("track_id")

        # Grouping key: prefer person label, fall back to track_id, then "scene"
        if person_label:
            key = f"person:{person_label}"
        elif track_id is not None:
            key = f"track:{track_id}"
        else:
            key = "scene:global"

        if key not in arcs:
            arcs[key] = []
        arcs[key].append(evt)

    # ── Build story arc objects ────────────────────────────────────────────────
    stories = []
    for idx, (key, arc_events) in enumerate(sorted(arcs.items())):
        # Sort by start time
        arc_events_sorted = sorted(
            arc_events,
            key=lambda e: e.get("start_ms") or e.get("timestamp_ms") or 0,
        )

        start_ms = arc_events_sorted[0].get("start_ms") or arc_events_sorted[0].get("timestamp_ms") or 0
        end_ms = arc_events_sorted[-1].get("end_ms") or arc_events_sorted[-1].get("start_ms") or start_ms
        duration_ms = max(0, end_ms - start_ms)

        # Derive person_label and track_id from key
        if key.startswith("person:"):
            person_label = key[7:]
            track_id = None
            # Try to find track_id from events
            for e in arc_events_sorted:
                if e.get("track_id") is not None:
                    track_id = e["track_id"]
                    break
        elif key.startswith("track:"):
            person_label = None
            track_id = int(key[6:]) if key[6:].isdigit() else key[6:]
        else:
            person_label = None
            track_id = None

        # Entry / exit direction
        first_evt = arc_events_sorted[0]
        last_evt = arc_events_sorted[-1]
        entry_direction = (first_evt.get("evidence") or {}).get("direction")
        exit_direction = (last_evt.get("evidence") or {}).get("direction")

        # Crop URL from first event with one
        crop_url = None
        for e in arc_events_sorted:
            ev_evidence = e.get("evidence") or {}
            crop = ev_evidence.get("crop_path") or ev_evidence.get("crop_url")
            if crop:
                crop_url = crop
                break

        # Human-readable summary
        event_types = list(dict.fromkeys(
            e.get("event_type") or e.get("type") or "event"
            for e in arc_events_sorted
        ))
        if len(event_types) == 1:
            summary = _event_label(event_types[0])
        elif len(event_types) <= 3:
            summary = " → ".join(_event_label(t) for t in event_types)
        else:
            summary = f"{_event_label(event_types[0])} → … → {_event_label(event_types[-1])}"

        # Confidence: average across arc events
        confidences = [e.get("confidence", 0) for e in arc_events_sorted if e.get("confidence")]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        # Slim event list for frontend (remove heavy evidence blobs)
        slim_events = []
        for e in arc_events_sorted:
            slim_events.append({
                "event_id": e.get("event_id") or e.get("id"),
                "event_type": e.get("event_type") or e.get("type"),
                "start_ms": e.get("start_ms") or e.get("timestamp_ms") or 0,
                "end_ms": e.get("end_ms"),
                "confidence": e.get("confidence"),
                "rule_name": e.get("rule_name"),
                "display_name": e.get("display_name") or _event_label(
                    e.get("event_type") or e.get("type") or "event"
                ),
            })

        stories.append({
            "story_id": f"STORY-{idx+1:03d}",
            "person_label": person_label,
            "track_id": track_id,
            "key": key,
            "events": slim_events,
            "event_count": len(arc_events_sorted),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": duration_ms,
            "start_formatted": _fmt_ms(start_ms),
            "end_formatted": _fmt_ms(end_ms),
            "summary": summary,
            "avg_confidence": round(avg_confidence, 3),
            "entry_direction": entry_direction,
            "exit_direction": exit_direction,
            "crop_url": crop_url,
        })

    # Sort by start_ms
    stories.sort(key=lambda s: s["start_ms"])

    return {
        "video_id": video_id,
        "filename": video.get("filename"),
        "status": "completed",
        "stories": stories,
        "total_stories": len(stories),
        "total_events": len(events),
    }
