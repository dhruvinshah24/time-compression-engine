"""
Pipeline Stage s03: Scene Change Detection — Phase 3A Implementation.

Reads extracted frame paths from context (populated by s02_extract),
runs the SceneChangeDetector, and stores the keyframe list in context
for downstream stages (s04_object_detect and beyond).

Algorithm: Adaptive Histogram Difference with Pixel Fallback.
Full rationale: research/algorithms.md → Phase 3A section.

Success criteria (from Phase 3A plan):
- Detects hard cuts reliably (composite > 0.7)
- Adaptive threshold handles shaky dashcam without false positives
- Duplicate frames removed before downstream AI processing
- Processing speed: target > 100 frames/second
"""

import logging
import time
from pathlib import Path

from app.engines.perception.change_detector.config import SceneChangeConfig
from app.engines.perception.change_detector.detector import SceneChangeDetector
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s03_scene_detect"


async def run(context: PipelineContext) -> StageResult:
    """
    Run scene change detection on the extracted frames.

    Reads from context:
        metadata["frame_paths"]     — list of frame file paths (from s02)
        metadata["fps"]             — video FPS (from s01)
        metadata["frame_skip_rate"] — extraction skip rate (from s02)

    Writes to context:
        metadata["keyframe_paths"]        — paths of frames selected as keyframes
        metadata["keyframe_numbers"]      — frame numbers of keyframes
        metadata["scene_boundaries"]      — frame numbers of detected boundaries
        metadata["duplicate_frame_count"] — number of duplicate frames removed
        metadata["scene_change_result"]   — full SceneChangeResult object
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting scene change detection for job {context.job_id}")

    # ── Step 1: Read from context ──────────────────────────────────────────
    frame_paths = context.metadata.get("frame_paths")
    if not frame_paths:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["frame_paths not found in context — s02_extract must run first"],
            logs=logs,
        )

    fps = float(context.metadata.get("fps", 25.0))
    frame_skip_rate = int(context.metadata.get("frame_skip_rate", 5))
    total_frames = len(frame_paths)

    logs.append(
        f"[{STAGE_NAME}] Analyzing {total_frames} frames at {fps:.2f}fps "
        f"(skip_rate={frame_skip_rate})"
    )

    # ── Step 2: Build config from system settings ──────────────────────────
    config = SceneChangeConfig(
        adaptive_k=float(context.settings.get("scene_change_adaptive_k", 1.5)),
        hard_cut_threshold=float(context.settings.get("scene_change_hard_cut_threshold", 0.70)),
        duplicate_threshold=float(context.settings.get("scene_change_duplicate_threshold", 0.02)),
    )
    logs.append(
        f"[{STAGE_NAME}] Config: adaptive_k={config.adaptive_k}, "
        f"hard_cut={config.hard_cut_threshold}, duplicate={config.duplicate_threshold}"
    )

    # ── Step 3: Run detection ──────────────────────────────────────────────
    detector = SceneChangeDetector(config=config)

    try:
        result = detector.detect(
            frame_paths=frame_paths,
            fps=fps,
            frame_skip_rate=frame_skip_rate,
        )
    except ImportError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[f"Required library not installed: {exc}. Run: pip install Pillow numpy"],
            logs=logs,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("Scene change detection failed for job %s", context.job_id)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[f"Scene change detection failed: {exc}"],
            logs=logs,
        )

    # ── Step 4: Store results in context ───────────────────────────────────
    context.metadata["keyframe_paths"] = result.keyframe_paths
    context.metadata["keyframe_numbers"] = result.keyframes
    context.metadata["scene_boundaries"] = result.scene_boundaries
    context.metadata["duplicate_frame_count"] = len(result.duplicate_frames)
    context.metadata["scene_change_result"] = result

    # ── Step 5: Validate and warn ──────────────────────────────────────────
    if not result.keyframes:
        warnings.append("No keyframes selected — all frames were classified as duplicates")
        logs.append(f"[{STAGE_NAME}] WARNING: Zero keyframes selected")
    else:
        logs.append(
            f"[{STAGE_NAME}] Scene boundaries: {len(result.scene_boundaries)}, "
            f"Duplicates removed: {len(result.duplicate_frames)}, "
            f"Keyframes: {len(result.keyframes)}"
        )

    metrics = result.to_metrics_dict()
    metrics["processing_time_ms"] = result.metrics.get("processing_time_ms", 0)
    metrics["processing_fps"] = result.metrics.get("processing_fps", 0.0)

    # ── Step 6: Save stage metrics (auto-save per mentor guidance) ─────────
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Completed in {duration_ms}ms "
        f"({metrics.get('processing_fps', 0):.1f} frames/s)"
    )

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
