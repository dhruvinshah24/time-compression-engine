"""Configuration for the Frame Extractor module."""
from dataclasses import dataclass


@dataclass
class FrameExtractorConfig:
    """
    Configuration for the Perception Engine's Frame Extractor.

    These are the module-level defaults. Per-job overrides come from
    the system_settings table (read via PipelineContext.settings).
    """
    default_skip_rate: int = 5          # Extract every Nth frame
    output_format: str = "jpg"          # Output image format
    jpeg_quality: int = 2               # FFmpeg quality scale (1=best, 31=worst)
    chunk_duration_s: int = 1800        # 30-minute chunks for long videos
    long_video_threshold_s: int = 3600  # 1 hour = use chunked extraction
    max_frames_per_job: int = 500_000   # Safety limit (prevents runaway jobs)
