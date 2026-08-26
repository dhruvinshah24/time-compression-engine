"""
Pipeline Stage s02: Frame Extraction — Phase 3 Implementation.

Responsibilities:
1. Read frame_skip_rate from system_settings (via context.settings)
2. Choose standard or chunked extraction based on video duration
3. Extract frames deterministically (same video + config = same frames)
4. Record per-frame metadata (frame number, timestamp_ms) to the DB
5. Report extraction speed in frames/second

Phase 3 addition: Adaptive Frame Skip (Pre-Extraction Streaming).
  When context.settings["adaptive_skip"] is True:
    1. Stream video at 320×180 using MOG2 background subtraction.
    2. Classify each frame into STATIC / LOW_MOTION / MEDIUM_MOTION /
       HIGH_MOTION / PROTECTED tiers.
    3. Return a list of frame indices to actually extract.
    4. Extract ONLY those frames via FFmpeg's select filter.
    This avoids writing and immediately discarding 80–90% of frames
    in static CCTV scenes.

  When adaptive_skip is False or video is > LONG_VIDEO_THRESHOLD_S:
    Falls back to fixed frame_skip_rate extraction (original behaviour).

Algorithm selection rationale:
- FFmpeg's 'select' filter (not -r resampling) is used for fixed extraction.
  Reason: -r produces resampled frames at a fixed rate, which can introduce
  duplicate frames from the original. 'select=not(mod(n,N))' picks exactly
  every Nth original frame — deterministic, no interpolation.

- For adaptive extraction: 'select=eq(n,10)+eq(n,25)+...' picks only the
  specific frame indices returned by AdaptiveSkipAnalyzer. This means FFmpeg
  still scans the full video (unavoidable without keyframe tricks) but writes
  only the selected frames.

- Chunked extraction is used for videos > 1 hour (configurable via
  LONG_VIDEO_THRESHOLD_S). Adaptive skip is disabled for chunked extraction
  in Phase 3 (too complex to combine; planned for Phase 4).

Why this matters for research:
- Deterministic extraction ensures that benchmark results are reproducible.
- Adaptive skip reduces frame I/O by ~60-80% on static CCTV (not yet validated
  on real footage — this is the Phase 3 research question).
"""

import logging
import time
from pathlib import Path

from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.ffmpeg import (
    FFmpegError,
    FrameExtractionConfig,
    VideoCorruptedError,
    extract_frames,
    extract_frames_by_indices,
    extract_frames_chunked,
)
from app.utils.storage import get_frames_dir

logger = logging.getLogger(__name__)

STAGE_NAME = "s02_extract"
LONG_VIDEO_THRESHOLD_S = 3600   # 1 hour — use chunked extraction above this
CHUNK_DURATION_S = 1800         # 30-minute chunks


async def run(context: PipelineContext) -> StageResult:
    """
    Extract frames from the validated video.

    Phase 3 change: when adaptive_skip=True in settings and video is short
    enough, runs pre-extraction motion analysis to select frame indices,
    then extracts only those frames. Falls back to fixed skip otherwise.

    On success: context.metadata["frames_dir"] and "frame_paths" are populated.
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []
    artifacts: list[str] = []

    video_path = Path(context.video_path)
    logs.append(f"[{STAGE_NAME}] Starting frame extraction for job {context.job_id}")

    # ── Step 1: Read configuration ─────────────────────────────────────────
    frame_skip_rate = int(context.settings.get("frame_skip_rate", 5))
    adaptive_skip_enabled = bool(context.settings.get("adaptive_skip", False))
    adaptive_skip_min = int(context.settings.get("adaptive_skip_min", 1))
    adaptive_skip_max = int(context.settings.get("adaptive_skip_max", 10))

    logs.append(
        f"[{STAGE_NAME}] frame_skip_rate={frame_skip_rate} "
        f"adaptive_skip={adaptive_skip_enabled}"
    )

    # ── Step 2: Get metadata from upstream stage ───────────────────────────
    meta = context.metadata.get("video_metadata")
    if meta is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["video_metadata not found in context — s01_upload must run first"],
            logs=logs,
        )

    # ── Step 2b: Classify processing profile ──────────────────────────────
    dur_s = meta.duration_seconds
    if dur_s <= 30:
        processing_profile = "QUICK_TEST"
        default_skip = 2
    elif dur_s <= 300:
        processing_profile = "SHORT"
        default_skip = 3
    elif dur_s <= 600:
        processing_profile = "STANDARD"
        default_skip = 5
    elif dur_s <= 3600:
        processing_profile = "LONG"
        default_skip = 10
    else:
        processing_profile = "EXTENDED"
        default_skip = 15

    # Settings override takes priority over profile default
    settings_skip = context.settings.get("frame_skip_rate")
    if settings_skip is not None:
        frame_skip_rate = int(settings_skip)
        skip_source = "settings"
    else:
        frame_skip_rate = default_skip
        skip_source = f"profile:{processing_profile}"

    context.metadata["processing_profile"] = processing_profile
    context.metadata["fps"] = getattr(meta, "fps", 25.0)

    is_long_video = meta.duration_seconds > LONG_VIDEO_THRESHOLD_S
    estimated_frames = max(1, meta.frame_count // max(frame_skip_rate, 1))
    logs.append(
        f"[{STAGE_NAME}] Video: {meta.duration_seconds:.1f}s, "
        f"{meta.frame_count} total frames, "
        f"~{estimated_frames} frames to extract"
    )
    logs.append(
        f"[{STAGE_NAME}] Profile: {processing_profile} | "
        f"frame_skip_rate: {frame_skip_rate} (source: {skip_source})"
    )

    # ── Step 3: Configure extraction ──────────────────────────────────────
    config = FrameExtractionConfig(
        frame_skip_rate=frame_skip_rate,
        output_format="jpg",
        quality=2,
    )

    frames_dir = get_frames_dir(context.job_id)
    logs.append(f"[{STAGE_NAME}] Output directory: {frames_dir}")

    # ── Step 4: Extract frames ─────────────────────────────────────────────
    all_frame_paths: list[str] = []
    extraction_errors: list[str] = []
    total_extraction_ms = 0
    adaptive_stats_dict: dict | None = None
    actual_skip_source = skip_source

    try:
        # ── 4a: Adaptive skip (pre-extraction streaming) ───────────────────
        # Only use adaptive skip when:
        # - enabled in settings
        # - video is not too long (chunked extraction used for EXTENDED)
        # - video file is accessible
        if adaptive_skip_enabled and not is_long_video:
            logs.append(f"[{STAGE_NAME}] Running pre-extraction adaptive skip analysis...")
            try:
                from app.utils.adaptive_skip import AdaptiveSkipConfig, select_frames_for_extraction

                adaptive_cfg = AdaptiveSkipConfig(
                    enabled=True,
                    min_skip=adaptive_skip_min,
                    max_skip=adaptive_skip_max,
                )
                frame_indices, adaptive_stats = select_frames_for_extraction(
                    str(video_path), config=adaptive_cfg,
                )
                adaptive_stats_dict = adaptive_stats.to_dict()

                logs.append(
                    f"[{STAGE_NAME}] Adaptive skip: selected {len(frame_indices)} "
                    f"of {adaptive_stats.total_video_frames} frames "
                    f"(ratio={adaptive_stats.effective_sampling_ratio:.2%}, "
                    f"protection_windows={adaptive_stats.protected_windows})"
                )

                if frame_indices:
                    # Extract only the selected frame indices
                    extract_start = time.perf_counter()
                    result = extract_frames_by_indices(
                        video_path,
                        frames_dir,
                        frame_indices,
                        output_format=config.output_format,
                        quality=config.quality,
                    )
                    all_frame_paths = result.frame_paths
                    total_extraction_ms = result.extraction_time_ms
                    if result.errors:
                        extraction_errors.extend(result.errors)
                    actual_skip_source = "adaptive"
                    logs.append(
                        f"[{STAGE_NAME}] Adaptive extraction: {len(all_frame_paths)} frames "
                        f"in {total_extraction_ms}ms"
                    )
                else:
                    # Adaptive returned 0 frames (very short video or analysis error)
                    # Fall back to fixed extraction
                    warnings.append(
                        "Adaptive skip returned 0 frames — falling back to fixed extraction"
                    )
                    adaptive_skip_enabled = False  # trigger fixed path below

            except Exception as exc:
                # Do not fail the pipeline if adaptive skip errors
                warnings.append(
                    f"Adaptive skip analysis failed ({type(exc).__name__}: {exc})"
                    f" — falling back to fixed frame_skip_rate={frame_skip_rate}"
                )
                logger.warning("[%s] Adaptive skip error: %s", STAGE_NAME, exc)
                adaptive_skip_enabled = False  # trigger fixed path below

        # ── 4b: Fixed skip rate or long video chunked extraction ────────────
        if not adaptive_skip_enabled or not all_frame_paths:
            if is_long_video:
                logs.append(
                    f"[{STAGE_NAME}] Long video detected ({meta.duration_seconds / 3600:.1f}h). "
                    f"Using chunked extraction ({CHUNK_DURATION_S // 60}min chunks). "
                    f"Adaptive skip disabled for chunked mode (Phase 3 limitation)."
                )
                for chunk_result in extract_frames_chunked(
                    video_path, frames_dir, config, meta, chunk_duration_s=CHUNK_DURATION_S
                ):
                    all_frame_paths.extend(chunk_result.frame_paths)
                    total_extraction_ms += chunk_result.extraction_time_ms
                    if chunk_result.errors:
                        extraction_errors.extend(chunk_result.errors)
                    logs.append(
                        f"[{STAGE_NAME}] Chunk complete: "
                        f"{chunk_result.total_frames_extracted} frames "
                        f"in {chunk_result.extraction_time_ms}ms "
                        f"({chunk_result.fps_achieved:.1f} fps)"
                    )
            else:
                result = extract_frames(video_path, frames_dir, config, meta)
                all_frame_paths = result.frame_paths
                total_extraction_ms = result.extraction_time_ms
                if result.errors:
                    extraction_errors.extend(result.errors)

    except VideoCorruptedError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[f"Frame extraction failed — video corrupted: {exc}"],
            logs=logs,
        )
    except FFmpegError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[f"FFmpeg error during extraction: {exc}"],
            logs=logs,
        )

    # ── Step 5: Validate output ────────────────────────────────────────────
    if not all_frame_paths:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["No frames were extracted — video may have no decodable content"],
            warnings=warnings,
            logs=logs,
        )

    # ── Step 6: Store results in context ───────────────────────────────────
    context.metadata["frames_dir"] = str(frames_dir)
    context.metadata["frame_paths"] = all_frame_paths
    context.metadata["frames_extracted"] = len(all_frame_paths)
    context.metadata["frame_skip_rate"] = frame_skip_rate

    artifacts.append(str(frames_dir))
    if extraction_errors:
        warnings.extend(extraction_errors)

    # ── Step 7: Compute metrics ────────────────────────────────────────────
    extraction_fps = (
        (len(all_frame_paths) / total_extraction_ms * 1000)
        if total_extraction_ms > 0 else 0.0
    )
    compression_preview = (
        meta.frame_count / len(all_frame_paths)
        if all_frame_paths else 0.0
    )

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Extracted {len(all_frame_paths)} frames "
        f"in {total_extraction_ms}ms ({extraction_fps:.1f} frames/s)"
    )
    logs.append(
        f"[{STAGE_NAME}] Frame reduction ratio: "
        f"{meta.frame_count} → {len(all_frame_paths)} "
        f"({compression_preview:.1f}x)"
    )
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms total")

    # Build metrics dict — adaptive skip stats included when available
    metrics: dict = {
        "frames_extracted":     len(all_frame_paths),
        "frame_skip_rate":      frame_skip_rate,
        "processing_profile":   processing_profile,
        "extraction_speed_fps": round(extraction_fps, 2),
        "extraction_time_ms":   total_extraction_ms,
        "frames_dir":           str(frames_dir),
        "estimated_frames":     estimated_frames,
        "frame_reduction_ratio": round(compression_preview, 2),
        "chunked_extraction":   is_long_video,
        # Phase 3: adaptive skip instrumentation
        "adaptive_skip_enabled": bool(actual_skip_source == "adaptive"),
        "skip_source":           actual_skip_source,
        "adaptive_skip_stats":   adaptive_stats_dict,
    }

    # Flatten key adaptive stats to top-level for easy diagnostics access
    if adaptive_stats_dict:
        metrics.update({
            "frames_examined_for_motion": adaptive_stats_dict.get("frames_examined"),
            "frames_selected":            adaptive_stats_dict.get("frames_selected"),
            "frames_skipped_by_adaptive": adaptive_stats_dict.get("frames_skipped"),
            "effective_sampling_ratio":   adaptive_stats_dict.get("effective_sampling_ratio"),
            "avg_motion_score_pct":       adaptive_stats_dict.get("average_motion_score_pct"),
            "max_motion_score_pct":       adaptive_stats_dict.get("maximum_motion_score_pct"),
            "protected_windows":          adaptive_stats_dict.get("protected_windows"),
        })

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms,
        warnings=warnings,
        errors=[],
        metrics=metrics,
        artifacts=artifacts,
        logs=logs,
    )
