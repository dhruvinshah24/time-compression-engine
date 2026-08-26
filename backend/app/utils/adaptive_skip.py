"""
Adaptive Frame Skip — Pre-Extraction Streaming Strategy.
Time Compression Engine v1.0.1 — Phase 3.

Philosophy:
  "Skip boring frames, never skip developing events."

Algorithm (pre-extraction streaming):
  1. Stream the video at reduced resolution (320×180) — no disk writes.
  2. Run MOG2 background subtraction per frame → motion fraction.
  3. Classify each frame into a motion tier:
       STATIC      < 0.5%  → sparse sampling
       LOW_MOTION  < 2%    → moderate sampling
       MEDIUM      < 8%    → dense sampling
       HIGH_MOTION ≥ 8%    → near-full sampling
       PROTECTED           → forced skip=1 (event developing)
  4. Apply EMA smoothing to avoid 1→10→1→10 oscillation.
  5. Return sorted list of frame INDICES to extract.
  6. FFmpeg then extracts ONLY those frames — no wasted JPEG writes.

Event Protection:
  When motion fraction spikes above protection_threshold OR an external
  signal fires (ROI proximity, new track, brightness change), enter
  PROTECTED mode: force skip=1 for the next protection_window_frames frames.
  This prevents fast events (person running, sudden entry) from being missed
  by adaptive under-sampling.

Status: IMPLEMENTED — unit tested with synthetic frames.
        NOT YET VALIDATED on real CCTV footage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ── Motion tier definitions ────────────────────────────────────────────────────
TIER_STATIC      = "STATIC"
TIER_LOW_MOTION  = "LOW_MOTION"
TIER_MEDIUM      = "MEDIUM_MOTION"
TIER_HIGH        = "HIGH_MOTION"
TIER_PROTECTED   = "PROTECTED"


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class AdaptiveSkipConfig:
    """Configuration for adaptive frame skip analysis."""
    enabled:                bool  = True

    # Per-tier skip rates (frames between samples).
    # skip=1 means every frame; skip=10 means 1 in 10 frames.
    static_skip:            int   = 10   # < 0.5% motion
    low_motion_skip:        int   = 6    # < 2%   motion
    medium_motion_skip:     int   = 3    # < 8%   motion
    high_motion_skip:       int   = 1    # ≥ 8%   motion
    protection_skip:        int   = 1    # PROTECTED mode — always process

    # EMA smoothing to prevent oscillation between skip rates.
    ema_alpha:              float = 0.25   # higher = faster response, more jitter
    warmup_frames:          int   = 25    # use medium_motion_skip during MOG2 warmup

    # Event protection — triggers on sudden motion or external signals.
    protection_threshold:   float = 0.08  # 8% pixel motion → enter PROTECTED
    protection_window_frames: int = 15    # frames to stay in PROTECTED after trigger

    # Hard bounds on skip rate.
    min_skip:               int   = 1
    max_skip:               int   = 15

    # Analysis resolution (downscaled for speed, not detection quality).
    analysis_width:         int   = 320
    analysis_height:        int   = 180


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class MotionScore:
    """Motion analysis result for a single frame."""
    frame_index:       int
    timestamp_ms:      float
    motion_fraction:   float     # fraction of pixels changed (0.0–1.0)
    motion_tier:       str       # STATIC / LOW_MOTION / MEDIUM_MOTION / HIGH_MOTION / PROTECTED
    raw_skip:          int       # skip rate from motion tier table
    smoothed_skip:     int       # after EMA smoothing
    protected:         bool      # True if in PROTECTED mode this frame
    protection_reason: Optional[str] = None


@dataclass
class AdaptiveSkipStats:
    """Aggregate statistics from an adaptive skip analysis pass."""
    total_video_frames:      int
    frames_examined:         int          # all frames fed to MOG2
    frames_selected:         int          # frames chosen for extraction
    frames_skipped:          int          # frames not selected
    effective_sampling_ratio: float       # frames_selected / total_video_frames
    average_motion_score:    float        # mean motion_fraction across examined frames
    maximum_motion_score:    float        # peak motion_fraction
    protected_windows:       int          # how many times protection was triggered
    protected_frames:        int          # total frames spent in PROTECTED mode
    skip_source:             str          # "adaptive" or "fixed"
    tier_distribution:       dict = field(default_factory=dict)  # tier → frame count

    def to_dict(self) -> dict:
        return {
            "total_video_frames":       self.total_video_frames,
            "frames_examined":          self.frames_examined,
            "frames_selected":          self.frames_selected,
            "frames_skipped":           self.frames_skipped,
            "effective_sampling_ratio": round(self.effective_sampling_ratio, 4),
            "average_motion_score_pct": round(self.average_motion_score * 100, 2),
            "maximum_motion_score_pct": round(self.maximum_motion_score * 100, 2),
            "protected_windows":        self.protected_windows,
            "protected_frames":         self.protected_frames,
            "skip_source":              self.skip_source,
            "tier_distribution":        self.tier_distribution,
        }


# ── Core Analyzer ─────────────────────────────────────────────────────────────

class AdaptiveSkipAnalyzer:
    """
    Streams a video at reduced resolution, computing per-frame motion scores.
    Returns frame indices to extract based on motion-tier skip policy.

    Usage:
        analyzer = AdaptiveSkipAnalyzer(config)
        selected_indices = analyzer.select_frames(video_path)
        stats = analyzer.stats
    """

    def __init__(self, config: AdaptiveSkipConfig | None = None) -> None:
        self.config = config or AdaptiveSkipConfig()
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset MOG2 and EMA state (call between videos)."""
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=200,
            varThreshold=30,
            detectShadows=False,
        )
        self._ema_skip: float = float(self.config.medium_motion_skip)
        self._frame_count: int = 0
        self._protection_remaining: int = 0
        self._protection_windows: int = 0
        self._protected_frames: int = 0
        self._motion_scores: list[MotionScore] = []

    # ── Public API ────────────────────────────────────────────────────────

    def select_frames(self, video_path: str) -> tuple[list[int], AdaptiveSkipStats]:
        """
        Stream video, compute motion per frame, return (selected_indices, stats).

        Args:
            video_path: path to video file.

        Returns:
            (sorted list of frame indices to extract, AdaptiveSkipStats)
        """
        self._reset_state()
        cfg = self.config

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error("[AdaptiveSkip] Cannot open: %s", video_path)
            return [], AdaptiveSkipStats(
                total_video_frames=0, frames_examined=0, frames_selected=0,
                frames_skipped=0, effective_sampling_ratio=0.0,
                average_motion_score=0.0, maximum_motion_score=0.0,
                protected_windows=0, protected_frames=0, skip_source="failed",
            )

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

        logger.info(
            "[AdaptiveSkip] Analyzing: %s | fps=%.1f total=%d",
            video_path, fps, total_frames,
        )

        selected: list[int] = []
        skip_counter = 0
        current_skip = cfg.medium_motion_skip
        frame_idx = 0
        tier_dist: dict[str, int] = {}

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_ms = (frame_idx / fps) * 1000.0
            score = self._compute_motion(frame, frame_idx, timestamp_ms)
            self._motion_scores.append(score)

            tier_dist[score.motion_tier] = tier_dist.get(score.motion_tier, 0) + 1

            if skip_counter == 0:
                # This frame is selected
                selected.append(frame_idx)
                current_skip = score.smoothed_skip
                skip_counter = current_skip

            skip_counter = max(0, skip_counter - 1)
            frame_idx += 1

        cap.release()

        # Build stats
        total = frame_idx  # actual frame count (may differ from CAP_PROP_FRAME_COUNT)
        fractions = [s.motion_fraction for s in self._motion_scores]
        avg_motion = sum(fractions) / len(fractions) if fractions else 0.0
        max_motion = max(fractions) if fractions else 0.0

        stats = AdaptiveSkipStats(
            total_video_frames=total,
            frames_examined=len(self._motion_scores),
            frames_selected=len(selected),
            frames_skipped=total - len(selected),
            effective_sampling_ratio=len(selected) / max(total, 1),
            average_motion_score=avg_motion,
            maximum_motion_score=max_motion,
            protected_windows=self._protection_windows,
            protected_frames=self._protected_frames,
            skip_source="adaptive" if cfg.enabled else "fixed",
            tier_distribution=tier_dist,
        )

        logger.info(
            "[AdaptiveSkip] Selected %d/%d frames (%.1f%%) | avg_motion=%.1f%% "
            "max_motion=%.1f%% protection_windows=%d",
            len(selected), total,
            stats.effective_sampling_ratio * 100,
            avg_motion * 100, max_motion * 100,
            self._protection_windows,
        )

        return sorted(selected), stats

    def trigger_protection(self, reason: str = "external") -> None:
        """
        Force PROTECTED mode from an external signal.

        External signals that can trigger this:
        - ROI proximity detected by a previous frame's tracking state
        - Sudden new track appearance
        - Brightness spike

        Call this BEFORE computing motion on the frame where protection
        should start. The protection window will cover subsequent frames.
        """
        if self._protection_remaining == 0:
            # Only count a new window; don't double-count re-triggers
            self._protection_windows += 1
        self._protection_remaining = self.config.protection_window_frames
        logger.debug("[AdaptiveSkip] Protection triggered: %s", reason)

    @property
    def is_protected(self) -> bool:
        return self._protection_remaining > 0

    @property
    def motion_scores(self) -> list[MotionScore]:
        return list(self._motion_scores)

    # ── Internal ──────────────────────────────────────────────────────────

    def _compute_motion(
        self,
        frame_bgr: np.ndarray,
        frame_idx: int,
        timestamp_ms: float,
    ) -> MotionScore:
        """Compute motion fraction and determine skip rate for one frame."""
        cfg = self.config

        # Downscale for speed — motion analysis does not need full resolution
        small = cv2.resize(
            frame_bgr,
            (cfg.analysis_width, cfg.analysis_height),
            interpolation=cv2.INTER_AREA,
        )
        fg_mask = self._mog2.apply(small)
        total_px = fg_mask.size
        changed_px = int(np.count_nonzero(fg_mask))
        motion_fraction = changed_px / max(total_px, 1)

        self._frame_count += 1

        # ── Warmup phase: MOG2 needs time to build background model ────────
        if frame_idx < cfg.warmup_frames:
            skip = cfg.medium_motion_skip
            tier = TIER_MEDIUM
            return MotionScore(
                frame_index=frame_idx,
                timestamp_ms=timestamp_ms,
                motion_fraction=motion_fraction,
                motion_tier=tier,
                raw_skip=skip,
                smoothed_skip=skip,
                protected=False,
            )

        # ── Disabled: use fixed medium skip rate ──────────────────────────────
        if not cfg.enabled:
            return MotionScore(
                frame_index=frame_idx,
                timestamp_ms=timestamp_ms,
                motion_fraction=motion_fraction,
                motion_tier=TIER_MEDIUM,
                raw_skip=cfg.medium_motion_skip,
                smoothed_skip=cfg.medium_motion_skip,
                protected=False,
            )

        # ── Event protection check ──────────────────────────────────────────
        if motion_fraction >= cfg.protection_threshold:
            if self._protection_remaining == 0:
                # New protection window triggered by motion spike
                self._protection_windows += 1
            self._protection_remaining = cfg.protection_window_frames

        protected = self._protection_remaining > 0
        if protected:
            self._protection_remaining -= 1
            self._protected_frames += 1
            return MotionScore(
                frame_index=frame_idx,
                timestamp_ms=timestamp_ms,
                motion_fraction=motion_fraction,
                motion_tier=TIER_PROTECTED,
                raw_skip=cfg.protection_skip,
                smoothed_skip=cfg.protection_skip,
                protected=True,
                protection_reason="motion_spike" if motion_fraction >= cfg.protection_threshold else "window",
            )

        # ── Motion tier classification ──────────────────────────────────────
        if motion_fraction < 0.005:
            tier, raw_skip = TIER_STATIC, cfg.static_skip
        elif motion_fraction < 0.020:
            tier, raw_skip = TIER_LOW_MOTION, cfg.low_motion_skip
        elif motion_fraction < cfg.protection_threshold:
            tier, raw_skip = TIER_MEDIUM, cfg.medium_motion_skip
        else:
            tier, raw_skip = TIER_HIGH, cfg.high_motion_skip

        raw_skip = max(cfg.min_skip, min(cfg.max_skip, raw_skip))

        # ── EMA smoothing to prevent oscillation ───────────────────────────
        alpha = cfg.ema_alpha
        self._ema_skip = alpha * raw_skip + (1.0 - alpha) * self._ema_skip
        smoothed_skip = max(cfg.min_skip, min(cfg.max_skip, round(self._ema_skip)))

        return MotionScore(
            frame_index=frame_idx,
            timestamp_ms=timestamp_ms,
            motion_fraction=motion_fraction,
            motion_tier=tier,
            raw_skip=raw_skip,
            smoothed_skip=smoothed_skip,
            protected=False,
        )


# ── Convenience function ──────────────────────────────────────────────────────

def select_frames_for_extraction(
    video_path: str,
    config: AdaptiveSkipConfig | None = None,
) -> tuple[list[int], AdaptiveSkipStats]:
    """
    Analyze video motion and return (frame_indices_to_extract, stats).

    This is the pre-extraction streaming interface. Call BEFORE FFmpeg
    frame extraction. Pass the returned indices to extract_frames_by_indices().

    Returns:
        (sorted list of int frame indices, AdaptiveSkipStats)
    """
    analyzer = AdaptiveSkipAnalyzer(config=config)
    return analyzer.select_frames(video_path)


def compute_adaptive_stats(motion_scores: list[MotionScore]) -> dict:
    """Compute summary statistics from a motion score list."""
    if not motion_scores:
        return {}
    fractions = [s.motion_fraction for s in motion_scores]
    skips = [s.smoothed_skip for s in motion_scores]
    tiers = {}
    for s in motion_scores:
        tiers[s.motion_tier] = tiers.get(s.motion_tier, 0) + 1
    return {
        "total_frames_analyzed": len(motion_scores),
        "avg_motion_pct":  round(sum(fractions) / len(fractions) * 100, 2),
        "max_motion_pct":  round(max(fractions) * 100, 2),
        "avg_skip":        round(sum(skips) / len(skips), 2),
        "min_skip":        min(skips),
        "max_skip":        max(skips),
        "tier_distribution": tiers,
        "protected_frames": sum(1 for s in motion_scores if s.protected),
    }
