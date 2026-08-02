"""
Pipeline Stage s07: Semantic Event Understanding — Phase 6 Implementation.

The first stage that answers "what happened?" rather than "what is visible?"

Reads the outputs of Phase 4 (tracks) and Phase 5 (motion profiles) and
produces a structured list of semantic Events, each with a documented
reason (the evidence dict) traceable back to a specific rule.

Success criteria (Phase 6):
  - Every confirmed track evaluated against all rules
  - Events contain rule_name for full audit trail
  - Evidence dict present on every event (explainability guarantee)
  - Camera motion frames optionally suppressed
  - Zero events returned for video with no objects (not an error)
"""

import logging
import time

from app.engines.semantic.event_understanding.config import EventUnderstandingConfig
from app.engines.semantic.event_understanding.engine import EventUnderstandingEngine
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s07_event_understand"


async def run(context: PipelineContext) -> StageResult:
    """
    Run semantic event understanding.

    Reads from context:
        metadata["all_tracks"]         — list of Track (from s05)
        metadata["motion_profiles"]    — dict[track_id, MotionProfile] (from s06)
        metadata["camera_motion_frames"] — list of frame numbers (from s06)

    Writes to context:
        metadata["event_result"]       — EventUnderstandingResult
        metadata["events"]             — list of Event
        metadata["events_by_type"]     — dict[event_type, count]
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting event understanding for job {context.job_id}")

    # ── Step 1: Read inputs ────────────────────────────────────────────────
    all_tracks = context.metadata.get("all_tracks")
    if all_tracks is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["all_tracks not in context — s05_track must run first"],
            logs=logs,
        )

    motion_profiles = context.metadata.get("motion_profiles", {})
    camera_motion_frames = context.metadata.get("camera_motion_frames", [])

    confirmed_count = sum(1 for t in all_tracks if t.is_confirmed)
    logs.append(
        f"[{STAGE_NAME}] {len(all_tracks)} total tracks, "
        f"{confirmed_count} confirmed, "
        f"{len(motion_profiles)} with motion profiles"
    )

    # ── Step 2: Configure engine ───────────────────────────────────────────
    config = EventUnderstandingConfig(
        min_event_confidence=float(
            context.settings.get("event_min_confidence", 0.4)
        ),
        min_track_frames_for_entry=int(
            context.settings.get("event_min_track_frames", 2)
        ),
        suppress_camera_motion_events=bool(
            context.settings.get("event_suppress_camera_motion", True)
        ),
    )

    # ── Step 3: Run event understanding ───────────────────────────────────
    engine = EventUnderstandingEngine(config=config)
    result = engine.understand(
        tracks=all_tracks,
        motion_profiles=motion_profiles,
        camera_motion_frames=camera_motion_frames,
    )

    # ── Step 4: Store in context ───────────────────────────────────────────
    context.metadata["event_result"] = result
    context.metadata["events"] = result.events
    context.metadata["events_by_type"] = result.events_by_type()

    # ── Step 5: Warnings ───────────────────────────────────────────────────
    if result.total_events == 0 and confirmed_count > 0:
        warnings.append(
            "Zero events generated despite confirmed tracks. "
            "Check min_event_confidence threshold or rule conditions."
        )
    if result.camera_motion_frames_skipped > 0:
        warnings.append(
            f"{result.camera_motion_frames_skipped} tracks suppressed "
            "due to camera motion overlap."
        )

    # ── Step 6: Metrics ────────────────────────────────────────────────────
    metrics = result.to_metrics_dict()
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Generated {result.total_events} events "
        f"from {confirmed_count} tracks"
    )
    logs.append(f"[{STAGE_NAME}] Event types: {result.events_by_type()}")
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
