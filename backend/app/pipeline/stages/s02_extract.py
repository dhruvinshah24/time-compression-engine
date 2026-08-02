"""
Pipeline Stage s02: Frame Extraction — Phase 2 Implementation.

Responsibilities:
1. Read frame_skip_rate from system_settings (via context.settings)
2. Choose standard or chunked extraction based on video duration
3. Extract frames deterministically (same video + config = same frames)
4. Record per-frame metadata (frame number, timestamp_ms) to the DB
5. Report extraction speed in frames/second

Algorithm selection rationale:
- FFmpeg's 'select' filter (not -r resampling) is used for frame extraction.
  Reason: -r produces resampled frames at a fixed rate, which can introduce
  duplicate frames from the original. 'select=not(mod(n,N))' picks exactly
  every Nth original frame — deterministic, no interpolation.

- Chunked extraction is used for videos > 1 hour (configurable via
  LONG_VIDEO_THRESHOLD_S). This keeps peak memory usage bounded by
  processing only 30 minutes of frames at a time before yielding.

- Frame filenames embed the frame number (frame_00000001.jpg) rather than
  a sequential extraction index. This preserves the relationship between
  filename and original video position, which is critical for timestamp
  recovery without re-reading the video file.

Why this matters for research:
- Deterministic extraction ensures that benchmark results are reproducible.
- Chunked processing allows 24-hour videos to be processed on commodity
  hardware without OOM errors.
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

    Reads frame_skip_rate from context.settings (populated from system_settings DB).
    Falls back to 5 if not configured.

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
    logs.append(f"[{STAGE_NAME}] frame_skip_rate={frame_skip_rate} (from system_settings)")

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

    is_long_video = meta.duration_seconds > LONG_VIDEO_THRESHOLD_S
    estimated_frames = max(1, meta.frame_count // frame_skip_rate)
    logs.append(
        f"[{STAGE_NAME}] Video: {meta.duration_seconds:.1f}s, "
        f"{meta.frame_count} total frames, "
        f"~{estimated_frames} frames to extract"
    )

    # ── Step 3: Configure extraction ──────────────────────────────────────
    config = FrameExtractionConfig(
        frame_skip_rate=frame_skip_rate,
        output_format="jpg",
        quality=2,  # High quality JPEG (lower number = better)
    )

    frames_dir = get_frames_dir(context.job_id)
    logs.append(f"[{STAGE_NAME}] Output directory: {frames_dir}")

    # ── Step 4: Extract frames ─────────────────────────────────────────────
    all_frame_paths: list[str] = []
    extraction_errors: list[str] = []
    total_extraction_ms = 0

    try:
        if is_long_video:
            logs.append(
                f"[{STAGE_NAME}] Long video detected ({meta.duration_seconds / 3600:.1f}h). "
                f"Using chunked extraction ({CHUNK_DURATION_S // 60}min chunks)."
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

    # Artifacts: record frames dir (not individual paths — too many for logs)
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

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms,
        warnings=warnings,
        errors=[],
        metrics={
            "frames_extracted": len(all_frame_paths),
            "frame_skip_rate": frame_skip_rate,
            "extraction_speed_fps": round(extraction_fps, 2),
            "extraction_time_ms": total_extraction_ms,
            "frames_dir": str(frames_dir),
            "estimated_frames": estimated_frames,
            "frame_reduction_ratio": round(compression_preview, 2),
            "chunked_extraction": is_long_video,
        },
        artifacts=artifacts,
        logs=logs,
    )
