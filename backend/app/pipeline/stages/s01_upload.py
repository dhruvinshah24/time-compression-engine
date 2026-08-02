"""
Pipeline Stage s01: Upload & Validate — Phase 2 Implementation.

Responsibilities:
1. Verify the uploaded file exists at the expected path
2. Run full validation (extension, size, corruption, codec, FPS, resolution)
3. Probe and store complete video metadata in the pipeline context
4. Extract a representative thumbnail for the UI
5. Populate context.metadata for downstream stages

Algorithm selection rationale:
- Validation is performed before any heavy processing to fail fast on bad inputs.
- ffprobe is used for metadata (not file headers) because it handles edge cases
  like variable FPS, non-standard containers, and missing moov atoms that
  simple header parsing misses.
- Thumbnail is extracted at 5% of video duration to avoid blank opening frames.

Why this approach over alternatives:
- python-magic for MIME type detection was considered but adds a binary
  dependency (libmagic). ffprobe's format detection is more comprehensive.
- moviepy was considered but adds heavy dependencies. subprocess + ffprobe
  gives the same metadata with zero extra libraries.
"""

import logging
import time
from pathlib import Path

from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.ffmpeg import (
    FFmpegError,
    FFmpegNotFoundError,
    VideoCorruptedError,
    extract_thumbnail,
    validate_video_file,
)
from app.utils.storage import get_thumbnails_dir

logger = logging.getLogger(__name__)

STAGE_NAME = "s01_upload"


async def run(context: PipelineContext) -> StageResult:
    """
    Validate the uploaded video and extract metadata.

    On success: context.metadata["video_metadata"] is populated with a
    VideoMetadata object. Downstream stages should read from there.

    On failure: returns StageResult(success=False) with error details.
    The pipeline orchestrator will not proceed to s02 if this stage fails.
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []
    artifacts: list[str] = []

    video_path = Path(context.video_path)
    logs.append(f"[{STAGE_NAME}] Starting validation for job {context.job_id}")
    logs.append(f"[{STAGE_NAME}] File: {video_path.name} ({video_path})")

    # ── Step 1: File existence ─────────────────────────────────────────────
    if not video_path.exists():
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[f"Video file not found at expected path: {video_path}"],
            logs=logs,
        )

    # ── Step 2: Full validation via ffprobe ────────────────────────────────
    logs.append(f"[{STAGE_NAME}] Running ffprobe validation...")
    try:
        validation = validate_video_file(video_path)
    except FFmpegNotFoundError as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[str(exc)],
            logs=logs,
        )

    if validation.rejected:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logs.append(f"[{STAGE_NAME}] Validation FAILED: {validation.errors}")
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=validation.errors,
            warnings=validation.warnings,
            logs=logs,
        )

    meta = validation.metadata
    warnings.extend(validation.warnings)

    logs.append(
        f"[{STAGE_NAME}] Validation passed: {meta.resolution} @ {meta.fps:.2f}fps, "
        f"{meta.duration_seconds:.1f}s, codec={meta.codec}"
    )

    # ── Step 3: Store metadata in context ─────────────────────────────────
    context.metadata["video_metadata"] = meta
    context.metadata["duration_seconds"] = meta.duration_seconds
    context.metadata["fps"] = meta.fps
    context.metadata["frame_count"] = meta.frame_count
    context.metadata["resolution"] = meta.resolution
    context.metadata["codec"] = meta.codec
    context.metadata["is_long_video"] = meta.is_long_video

    if meta.is_long_video:
        warnings.append(
            f"Video is {meta.duration_seconds / 3600:.1f} hours long. "
            f"Frame extraction will use chunked mode."
        )
        logs.append(f"[{STAGE_NAME}] Long video detected — chunked extraction will be used in s02")

    # ── Step 4: Extract thumbnail ──────────────────────────────────────────
    thumbnail_path = get_thumbnails_dir(context.job_id) / "upload_preview.jpg"
    thumbnail_ts = max(5.0, meta.duration_seconds * 0.05)

    try:
        extract_thumbnail(video_path, thumbnail_path, timestamp_s=thumbnail_ts)
        context.metadata["thumbnail_path"] = str(thumbnail_path)
        artifacts.append(str(thumbnail_path))
        logs.append(f"[{STAGE_NAME}] Thumbnail extracted at {thumbnail_ts:.1f}s → {thumbnail_path.name}")
    except (FFmpegError, VideoCorruptedError) as exc:
        warnings.append(f"Thumbnail extraction failed (non-fatal): {exc}")
        logs.append(f"[{STAGE_NAME}] WARNING: Thumbnail extraction failed: {exc}")

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms,
        warnings=warnings,
        errors=[],
        metrics={
            "file_size_bytes": meta.file_size_bytes,
            "duration_seconds": meta.duration_seconds,
            "fps": meta.fps,
            "frame_count": meta.frame_count,
            "resolution": meta.resolution,
            "codec": meta.codec,
            "has_audio": meta.has_audio,
            "is_long_video": meta.is_long_video,
        },
        artifacts=artifacts,
        logs=logs,
    )
