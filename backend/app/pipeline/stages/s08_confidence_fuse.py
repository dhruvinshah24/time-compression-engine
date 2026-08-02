"""
Pipeline Stage s08: Confidence Fusion — Phase 7 Implementation.

Reads events from Phase 6, enriches each with a 5-dimensional ConfidenceVector,
and filters out events below the fused confidence threshold.

The ConfidenceVector is stored in event.evidence["confidence_vector"] so
it is accessible in any later stage without re-computing it.

Success criteria (Phase 7):
  - Every event has a ConfidenceVector with all 5 dimensions populated
  - Fused confidence updates event.confidence (Phase 8 sees the fused value)
  - Events below threshold discarded but logged (not silently dropped)
  - Calibration statistics saved to reports for evaluation chapter
  - Configurable fusion strategy via system_settings
"""

import logging
import time

from app.engines.semantic.confidence_fusion.config import FusionConfig
from app.engines.semantic.confidence_fusion.fusion import ConfidenceFuser
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s08_confidence_fuse"


async def run(context: PipelineContext) -> StageResult:
    """
    Run confidence fusion on all Phase 6 events.

    Reads from context:
        metadata["events"]           — list of Event (from s07)
        metadata["all_tracks"]       — list of Track (from s05)
        metadata["motion_profiles"]  — dict[track_id, MotionProfile] (from s06)
        metadata["camera_motion_frames"] — list of frame numbers (from s06)

    Writes to context:
        metadata["fused_events"]      — events passing confidence threshold
        metadata["discarded_events"]  — events below threshold
        metadata["fusion_result"]     — FusionResult with calibration stats
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting confidence fusion for job {context.job_id}")

    # ── Step 1: Read inputs ────────────────────────────────────────────────
    events = context.metadata.get("events")
    if events is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["events not in context — s07_event_understand must run first"],
            logs=logs,
        )

    all_tracks = context.metadata.get("all_tracks", [])
    motion_profiles = context.metadata.get("motion_profiles", {})
    camera_motion_frames = context.metadata.get("camera_motion_frames", [])

    # Build track lookup dict
    track_lookup = {t.track_id: t for t in all_tracks}

    logs.append(
        f"[{STAGE_NAME}] {len(events)} events to fuse, "
        f"{len(track_lookup)} tracks, {len(motion_profiles)} motion profiles"
    )

    # ── Step 2: Configure fuser ────────────────────────────────────────────
    try:
        config = FusionConfig(
            w_detection=float(context.settings.get("fusion_w_detection", 0.30)),
            w_motion=float(context.settings.get("fusion_w_motion", 0.25)),
            w_rule=float(context.settings.get("fusion_w_rule", 0.20)),
            w_track_stability=float(context.settings.get("fusion_w_track_stability", 0.15)),
            w_scene_reliability=float(context.settings.get("fusion_w_scene_reliability", 0.10)),
            fusion_strategy=str(context.settings.get("fusion_strategy", "weighted_linear")),
            min_fused_confidence=float(context.settings.get("fusion_min_confidence", 0.35)),
        )
    except ValueError as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[f"FusionConfig validation failed: {e}"],
            logs=logs,
        )

    # ── Step 3: Run fusion ─────────────────────────────────────────────────
    fuser = ConfidenceFuser(config=config)
    result = fuser.fuse(
        events=list(events),  # work on a copy — we mutate event.confidence
        tracks=track_lookup,
        motion_profiles=motion_profiles,
        camera_motion_frames=camera_motion_frames,
    )

    # ── Step 4: Store in context ───────────────────────────────────────────
    context.metadata["fused_events"] = result.fused_events
    context.metadata["discarded_events"] = result.discarded_events
    context.metadata["fusion_result"] = result
    # Overwrite events with the fused + filtered list for Phase 8
    context.metadata["events"] = result.fused_events

    # ── Step 5: Warnings ───────────────────────────────────────────────────
    if result.total_discarded > 0:
        warnings.append(
            f"{result.total_discarded} events discarded by confidence fusion "
            f"(threshold={config.min_fused_confidence:.2f})."
        )
    if result.total_fused == 0 and events:
        warnings.append(
            "All events were discarded by confidence fusion. "
            "Consider lowering fusion_min_confidence in settings."
        )

    # ── Step 6: Metrics and calibration ───────────────────────────────────
    metrics = result.to_metrics_dict()
    metrics["fusion_strategy"] = config.fusion_strategy
    metrics["weights"] = {
        "detection": config.w_detection,
        "motion": config.w_motion,
        "rule": config.w_rule,
        "track_stability": config.w_track_stability,
        "scene_reliability": config.w_scene_reliability,
    }
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] {result.total_fused} events retained, "
        f"{result.total_discarded} discarded "
        f"(strategy={config.fusion_strategy})"
    )
    if result.fused_events:
        logs.append(
            f"[{STAGE_NAME}] Avg fused confidence: "
            f"{metrics.get('avg_fused_confidence', 0.0):.4f}"
        )
        logs.append(
            f"[{STAGE_NAME}] Dimension means: {metrics.get('dimension_means', {})}"
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
