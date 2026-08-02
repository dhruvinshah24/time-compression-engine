"""
Frame Extractor — Perception Engine, Time Compression Engine.

This module is the Perception Engine's interface to frame extraction.
It wraps the lower-level utils/ffmpeg.py functions and implements the
IntelligenceModule contract so it can be health-checked, metricked,
and swapped for alternative implementations.

Phase 2: Full implementation.
Phase 3: Will be extended to include scene change scoring per frame.
"""

import logging
import time
from pathlib import Path

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.perception.frame_extractor.config import FrameExtractorConfig
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.ffmpeg import (
    FFmpegError,
    FFmpegNotFoundError,
    FrameExtractionConfig,
    VideoCorruptedError,
    check_ffmpeg_available,
    extract_frames,
    extract_frames_chunked,
    get_ffmpeg_version,
)
from app.utils.storage import get_frames_dir

logger = logging.getLogger(__name__)


class FrameExtractor(IntelligenceModule):
    """
    Extracts video frames at a configurable skip rate.

    Belongs to: Perception Engine
    Phase:      2 (implemented)

    Design:
    - Delegates to utils/ffmpeg.py for the actual FFmpeg subprocess calls.
    - Maintains call metrics for the health check endpoint.
    - Automatically selects chunked mode for long videos.

    Extension point (Phase 3):
    - Override _post_process_frame() to compute per-frame brightness
      and motion scores as frames are extracted.
    """

    name = "FrameExtractor"
    version = "0.2.0"
    engine = "Perception Engine"

    def __init__(self, config: FrameExtractorConfig | None = None) -> None:
        self.config = config or FrameExtractorConfig()
        self._calls_total = 0
        self._total_frames_extracted = 0
        self._total_duration_ms = 0
        self._last_error: str | None = None
        self._ffmpeg_available: bool | None = None

    def _check_ffmpeg(self) -> bool:
        """Cache FFmpeg availability check."""
        if self._ffmpeg_available is None:
            try:
                check_ffmpeg_available()
                self._ffmpeg_available = True
            except FFmpegNotFoundError:
                self._ffmpeg_available = False
        return self._ffmpeg_available

    async def process(self, context: PipelineContext) -> StageResult:
        """
        Extract frames. Delegates to s02_extract stage logic.

        This method exists so the FrameExtractor can be called
        independently (e.g., in tests) outside the full pipeline.
        """
        from app.pipeline.stages import s02_extract
        return await s02_extract.run(context)

    def extract(
        self,
        video_path: str | Path,
        output_dir: str | Path,
        skip_rate: int | None = None,
        metadata=None,
    ) -> "FrameExtractionResult":
        """
        Direct extraction API (synchronous).

        Args:
            video_path:  Path to source video.
            output_dir:  Directory to write frames.
            skip_rate:   Override skip rate (uses config default if None).
            metadata:    Pre-computed VideoMetadata (avoids re-probing).

        Returns:
            FrameExtractionResult from utils/ffmpeg.py
        """
        from app.utils.ffmpeg import FrameExtractionResult  # local import for type hint

        start = time.perf_counter()
        self._calls_total += 1

        rate = skip_rate if skip_rate is not None else self.config.default_skip_rate
        config = FrameExtractionConfig(
            frame_skip_rate=rate,
            output_format=self.config.output_format,
            quality=self.config.jpeg_quality,
        )

        try:
            if metadata and metadata.is_long_video:
                # Chunked extraction — collect all results
                all_paths: list[str] = []
                total_ms = 0
                for chunk in extract_frames_chunked(
                    video_path, output_dir, config, metadata,
                    chunk_duration_s=self.config.chunk_duration_s,
                ):
                    all_paths.extend(chunk.frame_paths)
                    total_ms += chunk.extraction_time_ms

                from app.utils.ffmpeg import FrameExtractionResult
                result = FrameExtractionResult(
                    output_dir=str(output_dir),
                    total_frames_extracted=len(all_paths),
                    frame_paths=all_paths,
                    extraction_time_ms=total_ms,
                    config_used=config,
                )
            else:
                result = extract_frames(video_path, output_dir, config, metadata)

            self._total_frames_extracted += result.total_frames_extracted
            self._total_duration_ms += int((time.perf_counter() - start) * 1000)
            self._last_error = None
            return result

        except (FFmpegError, VideoCorruptedError) as exc:
            self._last_error = str(exc)
            raise

    def health_check(self) -> ModuleHealth:
        """
        Check FFmpeg availability.

        READY    — ffmpeg and ffprobe found on PATH.
        UNAVAILABLE — FFmpeg not installed.
        """
        if self._check_ffmpeg():
            return ModuleHealth.READY
        return ModuleHealth.UNAVAILABLE

    def get_metrics(self) -> ModuleMetrics:
        return ModuleMetrics(
            name=self.name,
            version=self.version,
            engine=self.engine,
            calls_total=self._calls_total,
            avg_duration_ms=(
                self._total_duration_ms / self._calls_total
                if self._calls_total > 0 else 0.0
            ),
            last_health=self.health_check(),
        )

    def get_ffmpeg_version(self) -> str:
        """Return the installed FFmpeg version string."""
        return get_ffmpeg_version()
