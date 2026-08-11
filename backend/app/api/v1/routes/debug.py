"""
Debug diagnostic route — exposes full pipeline internals for a video.

GET /api/v1/debug/{video_id}
    Returns: brightness timeline, track list, pose summary, all events
    with their sources. Used to verify detection quality.

GET /api/v1/debug/{video_id}/brightness
    Returns: per-frame brightness values + detected lighting events.
    Most useful for verifying light turn-on/off detection.
"""

import logging
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_video_repo, get_job_repo, get_event_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{video_id}")
async def debug_video(video_id: str):
    """Return full diagnostic information for a processed video."""
    video_repo = get_video_repo()
    job_repo   = get_job_repo()
    event_repo = get_event_repo()

    video = await video_repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    jobs = await job_repo.get_by_video(video_id)
    job = jobs[0] if jobs else None

    events = await event_repo.get_by_video(video_id)

    # Group events by source
    by_source: dict[str, list] = {}
    by_type:   dict[str, int]  = {}
    for evt in events:
        src = evt.get("rule_name", "unknown")
        by_source.setdefault(src, []).append({
            "event_type": evt.get("event_type", evt.get("type")),
            "start_ms": evt.get("start_ms", evt.get("timestamp_ms")),
            "end_ms": evt.get("end_ms"),
            "confidence": evt.get("confidence"),
            "evidence": evt.get("evidence"),
        })
        t = evt.get("event_type", evt.get("type", "unknown"))
        by_type[t] = by_type.get(t, 0) + 1

    # Stage metrics
    stage_metrics = {}
    metrics_dir = Path(
        f"C:/Users/dhruv/.gemini/antigravity/scratch/outputs/metrics"
    )
    if job:
        job_id = job.get("id", "")
        for stage in ["s04_object_detect", "s05_track", "s07_event_understand"]:
            mf = metrics_dir / job_id / f"{stage}.json"
            if mf.exists():
                try:
                    stage_metrics[stage] = json.loads(mf.read_text())
                except Exception:
                    pass

    return {
        "video_id": video_id,
        "filename": video.get("filename"),
        "file_path": video.get("file_path"),
        "metadata": video,
        "job": {
            "id": job.get("id") if job else None,
            "status": job.get("status") if job else None,
            "stages": job.get("stages") if job else [],
            "logs_tail": (job.get("logs") or [])[-30:] if job else [],
        },
        "events_total": len(events),
        "events_by_type": by_type,
        "events_by_source": {src: len(evts) for src, evts in by_source.items()},
        "events_detail": {src: evts for src, evts in by_source.items()},
        "stage_metrics": stage_metrics,
    }


@router.get("/{video_id}/brightness")
async def debug_brightness(video_id: str):
    """
    Run brightness analysis on the video's extracted frames and return
    the full per-frame brightness timeline. Useful for verifying that
    light turn-on/off events are being detected correctly.
    """
    video_repo = get_video_repo()
    video = await video_repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    frames_dir = video.get("frames_dir")
    if not frames_dir or not Path(frames_dir).exists():
        raise HTTPException(status_code=404, detail="Frames not found. Video must be processed first.")

    frames_dir_path = Path(frames_dir)
    frame_paths = sorted(frames_dir_path.glob("frame_*.jpg"))
    if not frame_paths:
        return {"brightness": [], "events": [], "message": "No frames found"}

    # Parse frame numbers from filenames
    fps = float(video.get("fps", 30.0))
    frame_skip = int(video.get("frame_skip_rate", 5))

    frame_numbers: list[int] = []
    timestamps_ms: list[float] = []
    for fp in frame_paths:
        stem = fp.stem  # e.g. "frame_00000010"
        try:
            fnum = int(stem.split("_")[1])
        except (IndexError, ValueError):
            fnum = len(frame_numbers) * frame_skip
        frame_numbers.append(fnum)
        timestamps_ms.append(fnum * 1000.0 / fps)

    from app.utils.brightness import analyze_frames, detect_lighting_events

    fb_list = analyze_frames(
        frame_paths=[str(p) for p in frame_paths],
        frame_numbers=frame_numbers,
        timestamps_ms=timestamps_ms,
    )

    # Detect with various thresholds for comparison
    events_t10  = detect_lighting_events(fb_list, brightness_threshold=10.0,  merge_gap_ms=800.0)
    events_t15  = detect_lighting_events(fb_list, brightness_threshold=15.0,  merge_gap_ms=800.0)
    events_t20  = detect_lighting_events(fb_list, brightness_threshold=20.0,  merge_gap_ms=800.0)

    # Subsample brightness for response size
    step = max(1, len(fb_list) // 100)
    brightness_sample = [
        {
            "frame": fb.frame_number,
            "timestamp_s": round(fb.timestamp_ms / 1000, 2),
            "raw": round(fb.raw_brightness, 1),
            "smoothed": round(fb.smoothed_brightness, 1),
            "baseline": round(fb.baseline_brightness, 1),
            "delta": round(fb.delta_from_baseline, 1),
        }
        for fb in fb_list[::step]
    ]

    def fmt_evt(e):
        return {
            "type": e.event_type,
            "timestamp_s": round(e.timestamp_ms / 1000, 2),
            "frame": e.frame_number,
            "brightness_before": e.brightness_before,
            "brightness_after": e.brightness_after,
            "delta": e.delta,
            "confidence": e.confidence,
        }

    return {
        "video_id": video_id,
        "total_frames_analyzed": len(fb_list),
        "brightness_range": {
            "min": round(min(fb.raw_brightness for fb in fb_list), 1) if fb_list else 0,
            "max": round(max(fb.raw_brightness for fb in fb_list), 1) if fb_list else 0,
            "mean": round(sum(fb.raw_brightness for fb in fb_list) / len(fb_list), 1) if fb_list else 0,
        },
        "events_at_threshold_10":  [fmt_evt(e) for e in events_t10],
        "events_at_threshold_15":  [fmt_evt(e) for e in events_t15],
        "events_at_threshold_20":  [fmt_evt(e) for e in events_t20],
        "brightness_timeline": brightness_sample,
        "note": "brightness_timeline sampled every ~1% of frames for response size",
    }
