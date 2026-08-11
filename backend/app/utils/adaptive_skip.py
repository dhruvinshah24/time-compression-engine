"""
Adaptive Frame Skip — Motion-based frame sampling rate control.

For 24-hour CCTV footage, static scenes can be safely sampled at 1fps
without missing any events. Running full YOLO detection on every 3rd frame
in a static room wastes 90% of compute.

Algorithm:
  1. Compute motion score for each frame using MOG2 background subtractor
     (pure OpenCV, no ML, <0.5ms per frame on CPU).
  2. Map motion score to a target skip rate:
       score < 0.5%  → skip=10  (static room,  ~1fps at 30fps)
       score < 2%    → skip=6   (micro-motion, ~2fps)
       score < 5%    → skip=4   (low activity, ~2.5fps)
       score < 12%   → skip=3   (walking,      ~3.3fps)
       score < 25%   → skip=2   (fast walking, ~5fps)
       score >= 25%  → skip=1   (running/crowd, full fps)
  3. Smooth the skip sequence with exponential moving average (alpha=0.3)
     to prevent oscillation (1→10→1→10 would drop frames during transitions).
  4. Return list of frame indices to extract.

This is a research contribution — produces a measurable speedup vs fixed skip
without sacrificing detection recall on active frames.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MotionScore:
    """Motion analysis result for a single frame."""
    frame_index: int
    timestamp_ms: float
    motion_fraction: float  # fraction of pixels that changed (0.0 to 1.0)
    raw_skip: int           # skip rate from motion table
    smoothed_skip: int      # after EMA smoothing


@dataclass
class AdaptiveSkipConfig:
    """Configuration for adaptive frame skipping."""
    enabled: bool = True
    min_skip: int = 1       # never skip less than this
    max_skip: int = 10      # never skip more than this
    ema_alpha: float = 0.3  # exponential smoothing factor (0=no change, 1=instant)
    warmup_frames: int = 30 # frames to build background model before adapting
    baseline_skip: int = 3  # fixed skip when disabled or during warmup


# Motion score → target skip rate mapping
_MOTION_TABLE = [
    (0.005,  10),  # < 0.5% pixels changed → nearly static
    (0.020,  6),   # < 2%  → micro-motion (leaves, screen flicker)
    (0.050,  4),   # < 5%  → low activity (person adjusting position)
    (0.120,  3),   # < 12% → normal walking
    (0.250,  2),   # < 25% → fast movement
    (1.000,  1),   # ≥ 25% → running, crowd, camera pan
]


class AdaptiveSkipAnalyzer:
    """
    Analyzes motion in a video and returns frame indices to process.
    
    Uses MOG2 background subtraction to compute motion fraction per frame.
    Background model adapts over time — handles gradual lighting changes.
    """

    def __init__(self, config: AdaptiveSkipConfig | None = None) -> None:
        self.config = config or AdaptiveSkipConfig()
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=200,
            varThreshold=30,
            detectShadows=False,  # shadows slow things down, not needed
        )
        self._ema_skip: float = float(self.config.baseline_skip)
        self._frame_count: int = 0

    def compute_motion(self, frame_bgr: np.ndarray, timestamp_ms: float = 0.0) -> MotionScore:
        """
        Compute motion fraction for a single frame.
        Returns MotionScore with smoothed skip recommendation.
        """
        # Resize to 320×180 for speed — motion analysis doesn't need full resolution
        small = cv2.resize(frame_bgr, (320, 180), interpolation=cv2.INTER_AREA)
        fg_mask = self._mog2.apply(small)
        
        # Count non-zero pixels (changed pixels)
        total_pixels = fg_mask.size
        changed_pixels = int(np.count_nonzero(fg_mask))
        motion_fraction = changed_pixels / max(total_pixels, 1)
        
        idx = self._frame_count
        self._frame_count += 1
        
        # During warmup: use baseline skip, still feed frames to MOG2
        if idx < self.config.warmup_frames:
            return MotionScore(
                frame_index=idx,
                timestamp_ms=timestamp_ms,
                motion_fraction=motion_fraction,
                raw_skip=self.config.baseline_skip,
                smoothed_skip=self.config.baseline_skip,
            )
        
        # Lookup raw skip from motion table
        raw_skip = self.config.baseline_skip
        for threshold, skip in _MOTION_TABLE:
            if motion_fraction < threshold:
                raw_skip = skip
                break
        
        # Clamp to configured bounds
        raw_skip = max(self.config.min_skip, min(self.config.max_skip, raw_skip))
        
        # Exponential moving average to smooth skip changes
        alpha = self.config.ema_alpha
        self._ema_skip = alpha * raw_skip + (1 - alpha) * self._ema_skip
        smoothed_skip = max(self.config.min_skip, min(self.config.max_skip, round(self._ema_skip)))
        
        return MotionScore(
            frame_index=idx,
            timestamp_ms=timestamp_ms,
            motion_fraction=motion_fraction,
            raw_skip=raw_skip,
            smoothed_skip=smoothed_skip,
        )

    def reset(self) -> None:
        """Reset background model and EMA state."""
        self._mog2 = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=30, detectShadows=False
        )
        self._ema_skip = float(self.config.baseline_skip)
        self._frame_count = 0


def select_frames_adaptive(
    video_path: str,
    config: AdaptiveSkipConfig | None = None,
    max_frames: int | None = None,
) -> list[tuple[int, float]]:
    """
    Analyze a video and return (frame_index, timestamp_ms) pairs to extract.
    
    Uses adaptive skip based on motion content.
    For static scenes: extracts ~1fps. For active scenes: up to full fps.
    
    Args:
        video_path:  Absolute path to video file.
        config:      AdaptiveSkipConfig. Uses defaults if None.
        max_frames:  Hard cap on extracted frames (for very long videos).
    
    Returns:
        List of (frame_number, timestamp_ms) to extract and process.
    """
    cfg = config or AdaptiveSkipConfig()
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error("[AdaptiveSkip] Cannot open video: %s", video_path)
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    logger.info(
        "[AdaptiveSkip] Analyzing %s: fps=%.1f total_frames=%d",
        video_path, fps, total_frames
    )
    
    analyzer = AdaptiveSkipAnalyzer(config=cfg)
    selected: list[tuple[int, float]] = []
    motion_scores: list[MotionScore] = []
    
    frame_idx = 0
    skip_counter = 0
    current_skip = cfg.baseline_skip
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        timestamp_ms = (frame_idx / fps) * 1000.0
        
        if skip_counter == 0:
            # This frame will be selected — compute motion
            score = analyzer.compute_motion(frame, timestamp_ms)
            motion_scores.append(score)
            selected.append((frame_idx, timestamp_ms))
            current_skip = score.smoothed_skip if cfg.enabled else cfg.baseline_skip
            skip_counter = current_skip
            
            if max_frames and len(selected) >= max_frames:
                break
        else:
            # Still compute motion on skipped frames to keep MOG2 model accurate
            analyzer.compute_motion(frame, timestamp_ms)
        
        skip_counter = max(0, skip_counter - 1)
        frame_idx += 1
    
    cap.release()
    
    # Log statistics
    if motion_scores:
        avg_motion = sum(s.motion_fraction for s in motion_scores) / len(motion_scores)
        avg_skip = sum(s.smoothed_skip for s in motion_scores) / len(motion_scores)
        logger.info(
            "[AdaptiveSkip] Selected %d/%d frames | avg_motion=%.1f%% avg_skip=%.1f",
            len(selected), total_frames,
            avg_motion * 100, avg_skip
        )
    
    return selected


def compute_motion_stats(motion_scores: list[MotionScore]) -> dict:
    """Compute summary statistics from motion score list for benchmarking."""
    if not motion_scores:
        return {}
    fractions = [s.motion_fraction for s in motion_scores]
    skips = [s.smoothed_skip for s in motion_scores]
    return {
        "total_frames_analyzed": len(motion_scores),
        "avg_motion_pct": round(sum(fractions) / len(fractions) * 100, 2),
        "max_motion_pct": round(max(fractions) * 100, 2),
        "avg_skip": round(sum(skips) / len(skips), 2),
        "min_skip": min(skips),
        "max_skip": max(skips),
    }
