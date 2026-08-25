"""
Low-Light Frame Preprocessor — TCE Accuracy Overhaul v1.0.1.

Applies quality-aware preprocessing BEFORE YOLO inference.
Mode is selected based on FrameQuality.quality_class from quality_analyzer.py.

Preprocessing strategy (per quality class):
  NORMAL           → no preprocessing (frame returned unchanged)
  LOW_LIGHT        → CLAHE on L-channel in LAB color space
  VERY_LOW_LIGHT   → CLAHE on L-channel + gamma correction (gamma=1.8)
  UNUSABLE         → no preprocessing + skip_detection=True

Why CLAHE instead of simple brightness boost?
  Simple boost (add constant): amplifies noise uniformly. On dark CCTV with
  sensor noise, this creates a snowstorm of false high-frequency detail.
  CLAHE (Contrast Limited Adaptive Histogram Equalization): equalizes contrast
  locally in small tiles (clipLimit prevents over-amplification), improving
  person silhouette visibility without noise explosion.

Why LAB color space for CLAHE?
  Applying CLAHE directly to BGR channels shifts color balance (a bright red
  becomes a very different color). In LAB, L is the luminance channel. Applying
  CLAHE only to L preserves the original hue and saturation while boosting
  perceptual contrast.

Why gamma correction?
  CLAHE is a local operation — it improves local contrast but may leave
  the global image dark. Gamma correction (gamma > 1.0 brightens the image)
  applies a global tone curve. For VERY_LOW_LIGHT, gamma=1.8 lifts mid-tones
  to the range where YOLO's feature extractors are most sensitive.

What we do NOT do:
  - We do not apply denoising (too slow for real-time, can smear edges)
  - We do not apply deep learning enhancement models (too much overhead)
  - We do not blindly apply enhancement to every frame (wastes GPU cycles
    and can make normal frames worse)

Branch: experiment/v1.0.1-accuracy-overhaul
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from app.utils.quality_analyzer import FrameQuality, QualityClass

logger = logging.getLogger(__name__)


@dataclass
class PreprocessedFrame:
    """
    Result of low-light preprocessing for a single frame.

    Fields:
        frame:               Preprocessed BGR numpy array (same shape as input).
        preprocessing_mode:  One of 'off', 'clahe', 'clahe_gamma'.
        skip_detection:      True if frame quality is UNUSABLE and inference should
                             be skipped. Caller should log the skip and continue.
        quality_class:       Original quality classification from the analyzer.
        original_mean_lum:   Mean luminance of the original frame (for logging).
        enhanced_mean_lum:   Mean luminance after preprocessing (0.0 if skip_detection).
    """
    frame: np.ndarray
    preprocessing_mode: str
    skip_detection: bool
    quality_class: QualityClass
    original_mean_lum: float
    enhanced_mean_lum: float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preprocess_frame(
    frame_bgr: np.ndarray,
    quality: FrameQuality,
    mode: str = "auto",
    clahe_clip_limit: float = 2.0,
    clahe_tile_size: tuple[int, int] = (8, 8),
    gamma: float = 1.8,
) -> PreprocessedFrame:
    """
    Apply quality-aware preprocessing to a single BGR frame.

    Args:
        frame_bgr:        OpenCV BGR frame as uint8 numpy array (H, W, 3).
        quality:          FrameQuality from quality_analyzer.analyze_frame().
        mode:             Preprocessing mode:
                            'auto'        — choose based on quality.quality_class
                            'clahe'       — always apply CLAHE (ignores quality class)
                            'clahe_gamma' — always apply CLAHE + gamma
                            'off'         — return raw frame unchanged
        clahe_clip_limit: CLAHE clip limit (prevents noise amplification).
                          Default 2.0; increase for very dark scenes.
        clahe_tile_size:  CLAHE tile grid size. Smaller = more local contrast.
        gamma:            Gamma value for gamma correction (only in clahe_gamma mode).
                          gamma > 1.0 = brighten (used for dark footage).

    Returns:
        PreprocessedFrame with the (possibly enhanced) frame and metadata.
    """
    if frame_bgr is None or frame_bgr.size == 0:
        empty = np.zeros((1, 1, 3), dtype=np.uint8)
        return PreprocessedFrame(
            frame=empty,
            preprocessing_mode="off",
            skip_detection=True,
            quality_class=quality.quality_class,
            original_mean_lum=quality.mean_luminance,
            enhanced_mean_lum=0.0,
        )

    orig_mean = quality.mean_luminance

    # Resolve mode
    if mode == "auto":
        resolved_mode = quality.recommended_preprocessing
    else:
        resolved_mode = mode

    # UNUSABLE frames: skip detection regardless of mode
    if quality.quality_class == QualityClass.UNUSABLE:
        return PreprocessedFrame(
            frame=frame_bgr,
            preprocessing_mode="off",
            skip_detection=True,
            quality_class=quality.quality_class,
            original_mean_lum=orig_mean,
            enhanced_mean_lum=orig_mean,
        )

    if resolved_mode == "off":
        return PreprocessedFrame(
            frame=frame_bgr,
            preprocessing_mode="off",
            skip_detection=False,
            quality_class=quality.quality_class,
            original_mean_lum=orig_mean,
            enhanced_mean_lum=orig_mean,
        )

    # Apply CLAHE
    enhanced = _apply_clahe(frame_bgr, clahe_clip_limit, clahe_tile_size)

    # Optionally apply gamma on top
    if resolved_mode == "clahe_gamma":
        enhanced = _apply_gamma(enhanced, gamma)

    # Compute enhanced mean luminance for logging
    try:
        import cv2
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        enh_mean = float(gray.mean())
    except Exception:
        enh_mean = orig_mean

    logger.debug(
        "[LowLight] mode=%s quality=%s lum: %.1f → %.1f",
        resolved_mode, quality.quality_class.value, orig_mean, enh_mean,
    )

    return PreprocessedFrame(
        frame=enhanced,
        preprocessing_mode=resolved_mode,
        skip_detection=False,
        quality_class=quality.quality_class,
        original_mean_lum=orig_mean,
        enhanced_mean_lum=round(enh_mean, 2),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _apply_clahe(
    frame_bgr: np.ndarray,
    clip_limit: float,
    tile_size: tuple[int, int],
) -> np.ndarray:
    """
    Apply CLAHE to the L channel of the LAB representation of the frame.

    Converting to LAB and applying CLAHE only to L (luminance) prevents
    color shifts that occur when CLAHE is applied directly to BGR channels.

    Returns a BGR uint8 array of the same shape as input.
    """
    try:
        import cv2
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
        l_enhanced = clahe.apply(l_channel)
        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    except Exception as exc:
        logger.warning("[LowLight] CLAHE failed, returning raw frame: %s", exc)
        return frame_bgr


def _apply_gamma(frame_bgr: np.ndarray, gamma: float) -> np.ndarray:
    """
    Apply gamma correction to a BGR uint8 frame.

    Formula: output = (input / 255.0) ** (1 / gamma) * 255
    gamma > 1.0 → brightens (lifts midtones)
    gamma < 1.0 → darkens

    Uses a precomputed lookup table (LUT) for efficiency (avoids per-pixel pow).
    """
    if gamma <= 0:
        return frame_bgr

    inv_gamma = 1.0 / gamma
    lut = np.array(
        [(i / 255.0) ** inv_gamma * 255 for i in range(256)],
        dtype=np.uint8,
    )

    try:
        import cv2
        return cv2.LUT(frame_bgr, lut)
    except Exception:
        # Fallback: index-based LUT
        return lut[frame_bgr]


def preprocess_frame_from_path(
    frame_path: str,
    frame_number: int = 0,
    timestamp_ms: float = 0.0,
    mode: str = "auto",
    **kwargs,
) -> PreprocessedFrame | None:
    """
    Convenience: load a frame from disk, run quality analysis, apply preprocessing.

    Returns None if the file cannot be read.
    """
    try:
        import cv2
        from app.utils.quality_analyzer import analyze_frame

        frame = cv2.imread(frame_path)
        if frame is None:
            return None

        quality = analyze_frame(frame, frame_number, timestamp_ms)
        return preprocess_frame(frame, quality, mode, **kwargs)

    except Exception as exc:
        logger.warning("[LowLight] Failed for %s: %s", frame_path, exc)
        return None
