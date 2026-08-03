"""
Pipeline Stage s05: Multi-Object Tracking — Phase 4 Implementation.

Processes all frame detections (from s04) in temporal order,
assigning consistent Track IDs and building the full track history.

The output of this stage is the foundation for Phase 6 (Semantic Event
Understanding) and Phase 8 (Event Graph). Every subsequent reasoning
step refers to tracks, not raw detections.

Success criteria (Phase 4):
- Consistent Track IDs across consecutive frames
- Track lifecycle states: created, active, lost, ended
- Basic occlusion tolerance (max_lost_frames)
- Metrics: track count, avg track length, avg confidence
- Zero detections → zero tracks (graceful empty case)
"""

import logging
import time

from app.engines.perception.tracker.config import TrackerConfig
from app.engines.perception.tracker.tracker import MultiObjectTracker, TrackingResult
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s05_track"


async def run(context: PipelineContext) -> StageResult:
    """
    Run multi-object tracking on frame detection results.

    Reads from context:
        metadata["frame_detections"]   — list of FrameDetectionResult (from s04)
        metadata["fps"]                — video FPS

    Writes to context:
        metadata["tracking_result"]    — TrackingResult
        metadata["all_tracks"]         — list of all Track objects
        metadata["active_tracks"]      — tracks still active at end
        metadata["ended_tracks"]       — tracks that were closed
        metadata["total_tracks"]       — total count
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting multi-object tracking for job {context.job_id}")

    # ── Step 1: Read frame detections ─────────────────────────────────────
    frame_detections = context.metadata.get("frame_detections")
    if frame_detections is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["frame_detections not in context — s04_object_detect must run first"],
            logs=logs,
        )

    total_input_detections = sum(r.detection_count for r in frame_detections)
    logs.append(
        f"[{STAGE_NAME}] Processing {len(frame_detections)} frames, "
        f"{total_input_detections} total detections"
    )

    # ── Step 2: Configure tracker ────────────────────────────────────────────
    config = TrackerConfig(
        iou_threshold=float(context.settings.get("tracker_iou_threshold", 0.20)),
        # Allow 30 missing frames before ending a track — bridges 1-second gaps
        # between sparse keyframes (28 keyframes over 31s = 1.1s per frame).
        max_lost_frames=int(context.settings.get("tracker_max_lost_frames", 30)),
        # 1 = confirm immediately on first detection. With sparse keyframes a person
        # may only appear in 2-3 frames total; requiring 2 consecutive means they
        # are never confirmed even when clearly visible.
        min_confirmation_frames=int(context.settings.get("tracker_min_confirmation_frames", 1)),
        # Must match detection_confidence. If detection fires at 0.40 confidence,
        # the tracker must accept 0.40 or it silently discards all detections.
        min_detection_confidence=float(
            context.settings.get("tracker_min_detection_confidence", 0.30)
        ),
    )
    logs.append(
        f"[{STAGE_NAME}] Config: iou={config.iou_threshold}, "
        f"max_lost={config.max_lost_frames}, confirm={config.min_confirmation_frames}, "
        f"min_conf={config.min_detection_confidence}"
    )

    # ── Step 3: Run tracking ───────────────────────────────────────────────
    try:
        from scipy.optimize import linear_sum_assignment  # noqa: F401
    except ImportError:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["scipy not installed. Run: pip install scipy"],
            logs=logs,
        )

    tracker = MultiObjectTracker(config=config)

    # Sort frames by frame_number to guarantee temporal order
    sorted_frames = sorted(frame_detections, key=lambda r: r.frame_number)

    for frame_result in sorted_frames:
        tracker.update(frame_result)

    result: TrackingResult = tracker.finalize()

    # ── Step 4: Store in context ───────────────────────────────────────────
    context.metadata["tracking_result"] = result
    context.metadata["all_tracks"] = result.all_tracks
    context.metadata["active_tracks"] = result.active_tracks
    context.metadata["ended_tracks"] = result.ended_tracks
    context.metadata["total_tracks"] = result.total_tracks_created

    # ── Step 5: Warnings ───────────────────────────────────────────────────
    if result.total_tracks_created == 0 and total_input_detections > 0:
        warnings.append(
            "Zero tracks created despite having detections. "
            "Check min_detection_confidence threshold."
        )
    elif result.total_tracks_created == 0:
        warnings.append("Zero tracks created — no detections from s04.")

    confirmed = result.confirmed_tracks
    if result.total_tracks_created > 0 and len(confirmed) == 0:
        warnings.append(
            "All tracks were tentative (never confirmed). "
            "Objects may not have appeared in enough consecutive frames. "
            "Consider reducing min_confirmation_frames."
        )

    # ── Step 6: Metrics and logging ───────────────────────────────────────
    metrics = result.to_metrics_dict()
    metrics["total_input_detections"] = total_input_detections

    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Created {result.total_tracks_created} tracks "
        f"({len(confirmed)} confirmed, {len(result.ended_tracks)} ended)"
    )
    logs.append(
        f"[{STAGE_NAME}] Classes tracked: {result._classes_tracked()}"
    )
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms,
        warnings=warnings,
        errors=[],
        metrics=metrics,
        artifacts=[],
        logs=logs,
    )
