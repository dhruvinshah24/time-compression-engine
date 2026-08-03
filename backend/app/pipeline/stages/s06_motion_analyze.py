"""
Pipeline Stage s06: Motion Analysis — Phase 5 Implementation.

Computes velocity, direction, speed class, and approach/recede signals
for every confirmed track. Detects camera-motion-dominated frames.

The motion profiles produced here are a direct input to Phase 6
(Semantic Event Understanding). The classifier in Phase 6 will use:
  - speed_class="fast" + class_name="person" → person_running
  - approach_signal="approaching" + class_name="car" → vehicle_approaching
  - is_stationary=True → idle_object / loitering (with time threshold)
  - camera_motion_frame → suppress event generation for that frame

Success criteria (Phase 5):
  - Every confirmed track gets a MotionProfile
  - SpeedClass classified for all tracks
  - Camera motion detection working on test corpus 05_camera_shake
  - Zero crashes on empty track list
"""

import logging
import time

from app.engines.perception.motion_analyzer.analyzer import MotionAnalyzer
from app.engines.perception.motion_analyzer.config import MotionAnalyzerConfig
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s06_motion_analyze"


async def run(context: PipelineContext) -> StageResult:
    """
    Run motion analysis on all confirmed tracks.

    Reads from context:
        metadata["all_tracks"]       — list of Track (from s05)
        metadata["tracking_result"]  — TrackingResult

    Writes to context:
        metadata["motion_result"]          — MotionAnalysisResult
        metadata["motion_profiles"]        — dict[track_id, MotionProfile]
        metadata["camera_motion_frames"]   — list of frame numbers
        metadata["stationary_track_ids"]   — track IDs classified as stationary
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting motion analysis for job {context.job_id}")

    # ── Step 1: Read tracks ────────────────────────────────────────────────
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

    # Include ENDED confirmed tracks — finalize() ends all tracks, so
    # confirmed tracks will be in ENDED state by the time s06 runs.
    confirmed = [
        t for t in all_tracks
        if (t.is_confirmed or t.confirmed_at_frame is not None)
        and len(t.observations) >= 1
    ]
    logs.append(
        f"[{STAGE_NAME}] {len(all_tracks)} total tracks, "
        f"{len(confirmed)} confirmed with ≥1 observations"
    )

    # ── Step 2: Configure analyzer ─────────────────────────────────────────
    config = MotionAnalyzerConfig(
        speed_stationary_max=float(
            context.settings.get("motion_speed_stationary_max", 0.01)
        ),
        speed_slow_max=float(
            context.settings.get("motion_speed_slow_max", 0.05)
        ),
        speed_walking_max=float(
            context.settings.get("motion_speed_walking_max", 0.15)
        ),
        area_change_threshold=float(
            context.settings.get("motion_area_change_threshold", 0.05)
        ),
        camera_motion_coherence_threshold=float(
            context.settings.get("motion_camera_coherence_threshold", 0.85)
        ),
    )

    # ── Step 3: Run analysis ───────────────────────────────────────────────
    analyzer = MotionAnalyzer(config=config)
    result = analyzer.analyze(all_tracks)

    # ── Step 4: Store in context ───────────────────────────────────────────
    context.metadata["motion_result"] = result
    context.metadata["motion_profiles"] = result.motion_profiles
    context.metadata["camera_motion_frames"] = result.camera_motion_frames
    context.metadata["stationary_track_ids"] = [
        tid for tid, p in result.motion_profiles.items() if p.is_stationary
    ]

    # ── Step 5: Warnings ───────────────────────────────────────────────────
    if not result.motion_profiles:
        warnings.append(
            "No motion profiles generated. "
            "Either no confirmed tracks, or all tracks had < 2 observations."
        )

    if result.camera_motion_frames:
        warnings.append(
            f"Camera motion detected in {len(result.camera_motion_frames)} frames. "
            "Events in these frames may be caused by camera movement, not scene activity."
        )

    # ── Step 6: Metrics ────────────────────────────────────────────────────
    metrics = result.to_metrics_dict()
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Analyzed {len(result.motion_profiles)} tracks: "
        f"{result.stationary_track_count} stationary, "
        f"{result.moving_track_count} moving"
    )
    logs.append(
        f"[{STAGE_NAME}] Speed distribution: {result._speed_distribution()}"
    )
    if result.camera_motion_frames:
        logs.append(
            f"[{STAGE_NAME}] Camera motion in {len(result.camera_motion_frames)} frames"
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
