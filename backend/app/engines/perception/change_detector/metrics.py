"""
Frame scoring metrics for Scene Change Detection — Phase 3A.

Implements two independent signals:
  1. Normalized pixel difference (spatial, fast)
  2. HSV histogram correlation difference (distributional, robust)

Both signals are used together because they capture different aspects:
- Pixel diff catches localized motion (a person walking)
- Histogram diff catches global scene shifts (lights turning on, camera cut)
- Using both reduces false positives from noise-only changes

Uses Pillow + NumPy only. No OpenCV dependency in Phase 3A.
OpenCV will be added in Phase 3B for object detection.

Performance notes:
- All images are resized to (224, 224) before computation.
  This gives a 70x speedup vs full-res 1920x1080 with negligible accuracy loss
  (validated against full-res on test corpus — see Phase 3A benchmark report).
- HSV histogram is computed on the resized image.
- Histogram comparison uses NumPy correlation (not cv2.compareHist).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Resize all frames to this before computation — speedup with minimal quality loss
_COMPUTE_SIZE = (224, 224)


@dataclass
class FrameScore:
    """
    Scoring result for a single frame relative to the previous frame.

    Includes decision_reason — the explainability field documenting exactly
    why the frame was classified the way it was. This supports the project's
    explainability objective and makes threshold debugging straightforward.

    frame_number:          Original frame number in the source video.
    frame_path:            Absolute path to the frame image file.
    timestamp_ms:          Estimated timestamp (frame_number * (1000 / fps)).
    pixel_diff_score:      Normalized mean absolute pixel difference [0, 1].
    histogram_diff_score:  HSV histogram correlation difference [0, 1].
    composite_score:       Weighted combination of both signals [0, 1].
    adaptive_threshold:    Threshold value at time of classification.
    is_hard_cut:           composite > hard_cut_threshold.
    is_scene_boundary:     composite > adaptive_threshold OR is_hard_cut.
    is_duplicate:          composite < duplicate_threshold.
    is_keyframe:           Selected for downstream processing.
    decision_reason:       Human-readable explanation of the classification.
    """
    frame_number: int
    frame_path: str
    timestamp_ms: float
    pixel_diff_score: float = 0.0
    histogram_diff_score: float = 0.0
    composite_score: float = 0.0
    adaptive_threshold: float = 0.0
    is_hard_cut: bool = False
    is_scene_boundary: bool = False
    is_duplicate: bool = False
    is_keyframe: bool = False
    decision_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "frame_number": self.frame_number,
            "timestamp_ms": self.timestamp_ms,
            "pixel_diff": round(self.pixel_diff_score, 4),
            "histogram_diff": round(self.histogram_diff_score, 4),
            "composite": round(self.composite_score, 4),
            "adaptive_threshold": round(self.adaptive_threshold, 4),
            "is_hard_cut": self.is_hard_cut,
            "is_scene_boundary": self.is_scene_boundary,
            "is_duplicate": self.is_duplicate,
            "is_keyframe": self.is_keyframe,
            "decision_reason": self.decision_reason,
        }


def load_frame(path: str | Path) -> np.ndarray:
    """
    Load a JPEG frame and return a resized uint8 numpy array (H, W, 3) in RGB.

    Raises:
        IOError: If the file cannot be opened (e.g., truncated JPEG).
    """
    img = Image.open(path).convert("RGB")
    img = img.resize(_COMPUTE_SIZE, Image.BILINEAR)
    return np.asarray(img, dtype=np.uint8)


def compute_pixel_diff(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """
    Compute normalized mean absolute difference between two grayscale frames.

    Args:
        frame_a: uint8 RGB array (H, W, 3)
        frame_b: uint8 RGB array (H, W, 3) — the later frame

    Returns:
        float in [0.0, 1.0] — 0.0 = identical, 1.0 = maximum difference
    """
    # Grayscale conversion using luminance weights (ITU-R BT.601)
    gray_a = 0.299 * frame_a[:, :, 0] + 0.587 * frame_a[:, :, 1] + 0.114 * frame_a[:, :, 2]
    gray_b = 0.299 * frame_b[:, :, 0] + 0.587 * frame_b[:, :, 1] + 0.114 * frame_b[:, :, 2]
    return float(np.mean(np.abs(gray_a - gray_b)) / 255.0)


def compute_histogram_diff(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    bins: int = 16,
) -> float:
    """
    Compute HSV color histogram correlation difference between two frames.

    The HSV color space separates hue (color identity) from saturation and value
    (brightness), making it more robust to lighting changes than RGB histograms.

    Args:
        frame_a: uint8 RGB array (H, W, 3)
        frame_b: uint8 RGB array (H, W, 3)
        bins:    Number of histogram bins per HSV channel.

    Returns:
        float in [0.0, 1.0] — 0.0 = identical distribution, 1.0 = fully different
    """
    hist_a = _compute_hsv_histogram(frame_a, bins)
    hist_b = _compute_hsv_histogram(frame_b, bins)
    correlation = _histogram_correlation(hist_a, hist_b)
    # Correlation of 1.0 = identical → diff of 0.0
    # Correlation of 0.0 = uncorrelated → diff of 1.0
    return float(np.clip(1.0 - correlation, 0.0, 1.0))


def _compute_hsv_histogram(frame_rgb: np.ndarray, bins: int) -> np.ndarray:
    """
    Compute a flattened HSV histogram for a RGB frame.

    Returns a 1D array of shape (bins * 3,), normalized to sum to 1.0.
    """
    img = Image.fromarray(frame_rgb).convert("HSV")
    arr = np.asarray(img, dtype=np.float32)

    hist_parts = []
    for channel in range(3):
        channel_data = arr[:, :, channel].flatten()
        h, _ = np.histogram(channel_data, bins=bins, range=(0, 256))
        hist_parts.append(h.astype(np.float32))

    hist = np.concatenate(hist_parts)
    total = hist.sum()
    if total > 0:
        hist = hist / total
    return hist


def _histogram_correlation(hist_a: np.ndarray, hist_b: np.ndarray) -> float:
    """
    Compute Pearson correlation between two normalized histograms.

    Equivalent to cv2.compareHist with HISTCMP_CORREL but implemented in NumPy.

    Returns float in [-1, 1]. For valid histograms: [0, 1].
    """
    mean_a = hist_a.mean()
    mean_b = hist_b.mean()
    num = ((hist_a - mean_a) * (hist_b - mean_b)).sum()
    denom = np.sqrt(
        ((hist_a - mean_a) ** 2).sum() * ((hist_b - mean_b) ** 2).sum()
    )
    if denom < 1e-10:
        return 1.0  # Both histograms are constant → treat as identical
    return float(num / denom)


def compute_composite_score(
    pixel_diff: float,
    histogram_diff: float,
    pixel_weight: float = 0.4,
    histogram_weight: float = 0.6,
) -> float:
    """
    Compute weighted composite score from the two signals.

    Args:
        pixel_diff:      Normalized pixel difference [0, 1]
        histogram_diff:  Histogram correlation difference [0, 1]
        pixel_weight:    Weight for pixel signal (default 0.4)
        histogram_weight: Weight for histogram signal (default 0.6)

    Returns:
        float in [0.0, 1.0]
    """
    return float(pixel_weight * pixel_diff + histogram_weight * histogram_diff)
