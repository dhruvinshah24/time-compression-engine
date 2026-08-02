"""
Scene Change Detector — Perception Engine, Phase 3A.

Core algorithm: Adaptive Histogram Difference with Pixel Fallback.
Full rationale: research/algorithms.md → Phase 3A section.

This module answers: "Where did the visual content meaningfully change?"

It does NOT do object detection or semantic understanding.
Those are Phases 3B and 6 respectively.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.perception.change_detector.config import SceneChangeConfig
from app.engines.perception.change_detector.metrics import (
    FrameScore,
    compute_composite_score,
    compute_histogram_diff,
    compute_pixel_diff,
    load_frame,
)
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


@dataclass
class SceneSegment:
    """
    A contiguous segment of video between two scene boundaries.

    Scene segments are the unit that downstream stages (object detection,
    semantic understanding) operate on, rather than isolated frames.
    This enables temporal reasoning within a segment context.

    Example:
        SceneSegment(index=0, start_frame=1, end_frame=425,
                     start_ms=0.0, end_ms=17000.0, duration_ms=17000.0,
                     keyframe_paths=[...], boundary_reason="start_of_video")
    """
    index: int
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float
    duration_ms: float
    keyframe_paths: list[str]
    boundary_reason: str = ""       # e.g. "hard_cut", "adaptive_threshold", "start_of_video"
    label: str = ""                 # optional semantic label (set by Phase 6+)

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "keyframe_count": len(self.keyframe_paths),
            "boundary_reason": self.boundary_reason,
        }


@dataclass
class SceneChangeResult:
    """
    Complete scene change analysis result for one video.

    scene_boundaries:   Frame numbers where a scene boundary was detected.
    scene_segments:     Contiguous video segments between boundaries.
    duplicate_frames:   Frame numbers classified as duplicates (skipped).
    keyframes:          Frame numbers selected for downstream processing.
    all_scores:         Full per-frame score list (for benchmarking/visualization).
    metrics:            Summary statistics.
    """
    scene_boundaries: list[int] = field(default_factory=list)
    scene_segments: list[SceneSegment] = field(default_factory=list)
    duplicate_frames: list[int] = field(default_factory=list)
    keyframes: list[int] = field(default_factory=list)
    keyframe_paths: list[str] = field(default_factory=list)
    all_scores: list[FrameScore] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_metrics_dict(self) -> dict:
        return {
            "total_frames_analyzed": self.metrics.get("total_frames", 0),
            "scene_boundaries_detected": len(self.scene_boundaries),
            "scene_segments": len(self.scene_segments),
            "hard_cuts_detected": self.metrics.get("hard_cuts", 0),
            "duplicate_frames": len(self.duplicate_frames),
            "keyframes_selected": len(self.keyframes),
            "duplicate_rate": self.metrics.get("duplicate_rate", 0.0),
            "reduction_ratio": self.metrics.get("reduction_ratio", 0.0),
            "avg_composite_score": self.metrics.get("avg_composite", 0.0),
        }


class AdaptiveThreshold:
    """
    Rolling-window adaptive threshold calculator.

    Computes threshold as: mean(window) + k * std(window)

    This approach adapts to the local noise floor of each video segment,
    rather than assuming a single global threshold works for all video types.
    """

    def __init__(self, window: int = 50, k: float = 1.5) -> None:
        self.window = window
        self.k = k
        self._scores: deque[float] = deque(maxlen=window)
        # Pre-fill with a neutral value to avoid edge effects on the first N frames
        self._scores.extend([0.05] * window)

    def update(self, score: float) -> None:
        """Add a new score to the rolling window."""
        self._scores.append(score)

    def threshold(self) -> float:
        """Compute current adaptive threshold from the rolling window."""
        arr = np.array(self._scores)
        return float(arr.mean() + self.k * arr.std())

    def __repr__(self) -> str:
        arr = np.array(self._scores)
        return (
            f"AdaptiveThreshold(window={self.window}, k={self.k}, "
            f"current_threshold={self.threshold():.4f}, "
            f"window_mean={arr.mean():.4f}, window_std={arr.std():.4f})"
        )


class SceneChangeDetector(IntelligenceModule):
    """
    Detects scene boundaries in an extracted frame sequence.

    Belongs to: Perception Engine
    Phase: 3A (implemented)

    Input:  Ordered list of frame paths (output of s02_extract).
    Output: SceneChangeResult with boundaries, duplicates, and keyframes.

    Design decisions:
    - Uses Pillow + NumPy only (no OpenCV until Phase 3B).
    - Resizes frames to 224×224 for compute efficiency.
    - Two signals (pixel diff + histogram diff) reduce false positives.
    - Adaptive threshold adapts to each video's noise floor.
    - First frame is always a keyframe (establishes scene baseline).

    Extension points (Phase 5+):
    - Override _compute_scores() to add motion vector signal.
    - Override _classify() to add temporal smoothing.
    """

    name = "SceneChangeDetector"
    version = "0.3.0"
    engine = "Perception Engine"

    def __init__(self, config: SceneChangeConfig | None = None) -> None:
        self.config = config or SceneChangeConfig()
        self._calls_total = 0
        self._total_frames_processed = 0
        self._total_duration_ms = 0
        self._last_error: str | None = None
        self._libs_available: bool | None = None

    def _check_libs(self) -> bool:
        if self._libs_available is None:
            try:
                import PIL  # noqa: F401
                import numpy  # noqa: F401
                self._libs_available = True
            except ImportError:
                self._libs_available = False
        return self._libs_available

    def detect(
        self,
        frame_paths: list[str],
        fps: float = 25.0,
        frame_skip_rate: int = 5,
    ) -> SceneChangeResult:
        """
        Run scene change detection on a list of frame paths.

        Args:
            frame_paths:      Ordered list of frame paths (output of s02_extract).
            fps:              Video FPS (used to compute timestamps).
            frame_skip_rate:  Skip rate used during extraction (for timestamp recovery).

        Returns:
            SceneChangeResult with full scoring and classification.
        """
        self._calls_total += 1
        start = time.perf_counter()

        if not frame_paths:
            return SceneChangeResult(metrics={"total_frames": 0})

        cfg = self.config
        adaptive = AdaptiveThreshold(window=cfg.adaptive_window, k=cfg.adaptive_k)

        scores: list[FrameScore] = []
        prev_frame_array = None

        # Process frames one at a time — O(1) memory
        for idx, path in enumerate(frame_paths):
            # Recover original frame number from filename (frame_XXXXXXXX.jpg)
            frame_number = _extract_frame_number(path, idx)
            timestamp_ms = (frame_number * frame_skip_rate * 1000.0) / fps

            try:
                curr_array = load_frame(path)
            except Exception as exc:
                logger.warning("Failed to load frame %s: %s", path, exc)
                # Score as duplicate to skip, don't crash the pipeline
                scores.append(FrameScore(
                    frame_number=frame_number,
                    frame_path=path,
                    timestamp_ms=timestamp_ms,
                    is_duplicate=True,
                ))
                continue

            if prev_frame_array is None:
                # First frame — always a keyframe, no diff to compute
                score = FrameScore(
                    frame_number=frame_number,
                    frame_path=path,
                    timestamp_ms=timestamp_ms,
                    adaptive_threshold=0.0,
                    is_keyframe=True,
                    decision_reason="first_frame",
                )
                scores.append(score)
                prev_frame_array = curr_array
                continue

            # Compute two signals
            pixel_diff = compute_pixel_diff(prev_frame_array, curr_array)
            hist_diff = compute_histogram_diff(
                prev_frame_array, curr_array, bins=cfg.histogram_bins
            )
            composite = compute_composite_score(
                pixel_diff, hist_diff, cfg.pixel_weight, cfg.histogram_weight
            )

            current_threshold = adaptive.threshold()

            # Classify
            is_hard_cut = composite > cfg.hard_cut_threshold
            is_boundary = is_hard_cut or (composite > current_threshold)
            is_duplicate = composite < cfg.duplicate_threshold

            # Build decision reason (explainability)
            if is_duplicate:
                reason = (
                    f"duplicate: composite={composite:.4f} < "
                    f"duplicate_threshold={cfg.duplicate_threshold}"
                )
            elif is_hard_cut:
                reason = (
                    f"hard_cut: composite={composite:.4f} > "
                    f"hard_cut_threshold={cfg.hard_cut_threshold}"
                )
            elif is_boundary:
                reason = (
                    f"adaptive_boundary: composite={composite:.4f} > "
                    f"adaptive_threshold={current_threshold:.4f} "
                    f"(window_mean+{cfg.adaptive_k}*std)"
                )
            else:
                reason = (
                    f"normal: composite={composite:.4f}, "
                    f"threshold={current_threshold:.4f}"
                )

            score = FrameScore(
                frame_number=frame_number,
                frame_path=path,
                timestamp_ms=timestamp_ms,
                pixel_diff_score=pixel_diff,
                histogram_diff_score=hist_diff,
                composite_score=composite,
                adaptive_threshold=current_threshold,
                is_hard_cut=is_hard_cut,
                is_scene_boundary=is_boundary,
                is_duplicate=is_duplicate,
                is_keyframe=is_boundary and not is_duplicate,
                decision_reason=reason,
            )
            scores.append(score)
            adaptive.update(composite)
            prev_frame_array = curr_array

        # Post-process: enforce min_scene_duration and collect results
        result = self._build_result(scores, cfg)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._total_frames_processed += len(frame_paths)
        self._total_duration_ms += elapsed_ms

        logger.info(
            "SceneChangeDetector: %d frames → %d boundaries, %d duplicates, "
            "%d keyframes in %dms",
            len(frame_paths),
            len(result.scene_boundaries),
            len(result.duplicate_frames),
            len(result.keyframes),
            elapsed_ms,
        )

        result.metrics["processing_time_ms"] = elapsed_ms
        result.metrics["processing_fps"] = (
            len(frame_paths) / elapsed_ms * 1000 if elapsed_ms > 0 else 0.0
        )
        return result

    def _build_result(
        self,
        scores: list[FrameScore],
        cfg: SceneChangeConfig,
    ) -> SceneChangeResult:
        """
        Build SceneChangeResult from scored frames.

        Applies min_scene_duration filter and constructs SceneSegments
        from the boundary list.
        """
        scene_boundaries: list[int] = []
        duplicate_frames: list[int] = []
        keyframes: list[int] = []
        keyframe_paths: list[str] = []
        hard_cuts = 0
        last_boundary_idx = -cfg.min_scene_duration_frames

        for score in scores:
            if score.is_duplicate:
                duplicate_frames.append(score.frame_number)
                if cfg.include_duplicate_frames:
                    keyframes.append(score.frame_number)
                    keyframe_paths.append(score.frame_path)
            elif score.is_keyframe or score.frame_number == scores[0].frame_number:
                if (score.frame_number - last_boundary_idx) >= cfg.min_scene_duration_frames:
                    if score.is_scene_boundary:
                        scene_boundaries.append(score.frame_number)
                        last_boundary_idx = score.frame_number
                    if score.is_hard_cut:
                        hard_cuts += 1
                    keyframes.append(score.frame_number)
                    keyframe_paths.append(score.frame_path)
            elif not score.is_duplicate:
                keyframes.append(score.frame_number)
                keyframe_paths.append(score.frame_path)

        # Build scene segments between boundary frames
        segments = self._build_segments(scores, scene_boundaries, keyframe_paths)

        total = len(scores)
        composite_scores = [s.composite_score for s in scores if s.composite_score > 0]

        metrics = {
            "total_frames": total,
            "hard_cuts": hard_cuts,
            "duplicate_rate": len(duplicate_frames) / total if total > 0 else 0.0,
            "reduction_ratio": total / len(keyframes) if keyframes else 0.0,
            "avg_composite": float(np.mean(composite_scores)) if composite_scores else 0.0,
            "max_composite": float(np.max(composite_scores)) if composite_scores else 0.0,
        }

        return SceneChangeResult(
            scene_boundaries=scene_boundaries,
            scene_segments=segments,
            duplicate_frames=duplicate_frames,
            keyframes=keyframes,
            keyframe_paths=keyframe_paths,
            all_scores=scores,
            metrics=metrics,
        )

    def _build_segments(
        self,
        scores: list[FrameScore],
        boundaries: list[int],
        all_keyframe_paths: list[str],
    ) -> list[SceneSegment]:
        """
        Construct contiguous SceneSegments from the boundary list.

        Each segment spans from one boundary frame to the next.
        Keyframe paths within each segment's time window are assigned to it.
        """
        if not scores:
            return []

        # Build a frame_number → score lookup
        frame_map: dict[int, FrameScore] = {s.frame_number: s for s in scores}
        path_by_frame: dict[int, str] = {s.frame_number: s.frame_path for s in scores}

        # Boundary points: always include the first and last frame
        boundary_frames = [scores[0].frame_number] + boundaries
        last_frame = scores[-1].frame_number

        segments: list[SceneSegment] = []
        for seg_idx, start_frame in enumerate(boundary_frames):
            # End is the next boundary minus 1, or the last frame
            if seg_idx + 1 < len(boundary_frames):
                end_frame = boundary_frames[seg_idx + 1] - 1
            else:
                end_frame = last_frame

            start_score = frame_map.get(start_frame)
            end_score = frame_map.get(end_frame)

            start_ms = start_score.timestamp_ms if start_score else 0.0
            end_ms = end_score.timestamp_ms if end_score else start_ms

            # Collect keyframes that fall within this segment's range
            seg_keyframe_paths = [
                s.frame_path
                for s in scores
                if start_frame <= s.frame_number <= end_frame and s.is_keyframe
            ]

            boundary_reason = "start_of_video" if seg_idx == 0 else (
                frame_map[start_frame].decision_reason
                if start_frame in frame_map else "scene_boundary"
            )

            segments.append(SceneSegment(
                index=seg_idx,
                start_frame=start_frame,
                end_frame=end_frame,
                start_ms=start_ms,
                end_ms=end_ms,
                duration_ms=end_ms - start_ms,
                keyframe_paths=seg_keyframe_paths,
                boundary_reason=boundary_reason,
            ))

        return segments

    async def process(self, context: PipelineContext) -> StageResult:
        """IntelligenceModule contract — delegates to s03_scene_detect stage."""
        from app.pipeline.stages import s03_scene_detect
        return await s03_scene_detect.run(context)

    def health_check(self) -> ModuleHealth:
        if self._check_libs():
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


def _extract_frame_number(path: str, fallback: int) -> int:
    """
    Extract the original frame number from a frame filename.

    Expected format: frame_00000042.jpg → 42
    Falls back to the extraction index if filename doesn't match.
    """
    stem = Path(path).stem  # e.g. "frame_00000042"
    if stem.startswith("frame_"):
        try:
            return int(stem.split("_")[1])
        except (IndexError, ValueError):
            pass
    return fallback
