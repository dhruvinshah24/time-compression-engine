"""
Unit tests for low_light.py — TCE Accuracy Overhaul v1.0.1.

Tests verify:
  - mode='off' returns frame unchanged
  - UNUSABLE quality → skip_detection=True regardless of mode
  - CLAHE does not crash on any frame size
  - CLAHE output shape == input shape
  - Gamma correction lightens dark frames
  - mode='auto' uses quality class to decide
  - preprocess_frame_from_path: missing file returns None
  - PreprocessedFrame has all required fields

No GPU required. No real video files required.
"""

import numpy as np
import pytest

from app.utils.quality_analyzer import (
    FrameQuality,
    QualityClass,
    QualityThresholds,
)
from app.utils.low_light import (
    preprocess_frame,
    preprocess_frame_from_path,
    PreprocessedFrame,
    _apply_clahe,
    _apply_gamma,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def make_quality(
    quality_class: QualityClass,
    mean_lum: float = 100.0,
    preprocessing: str = "off",
) -> FrameQuality:
    """Create a FrameQuality with the given class and preprocessing recommendation."""
    mode_map = {
        QualityClass.NORMAL:         "off",
        QualityClass.LOW_LIGHT:      "clahe",
        QualityClass.VERY_LOW_LIGHT: "clahe_gamma",
        QualityClass.UNUSABLE:       "off",
    }
    rec = preprocessing if preprocessing != "off" else mode_map[quality_class]
    return FrameQuality(
        frame_number=0,
        timestamp_ms=0.0,
        mean_luminance=mean_lum,
        luminance_std=20.0,
        blur_score=100.0,
        dark_pixel_ratio=0.1,
        histogram_spread=100.0,
        quality_class=quality_class,
        recommended_preprocessing=rec,
    )


def make_dark_frame(h: int = 100, w: int = 100) -> np.ndarray:
    """Dark BGR frame (mean luma ~30)."""
    return np.full((h, w, 3), 30, dtype=np.uint8)


def make_normal_frame(h: int = 100, w: int = 100) -> np.ndarray:
    """Normal brightness BGR frame (mean luma ~128)."""
    rng = np.random.default_rng(42)
    return rng.integers(80, 180, (h, w, 3), dtype=np.uint8)


# ── PreprocessedFrame field tests ──────────────────────────────────────────

class TestPreprocessedFrameFields:

    def test_mode_off_returns_raw_frame(self):
        """mode='off' returns the original frame unchanged."""
        frame = make_normal_frame()
        quality = make_quality(QualityClass.NORMAL)
        result = preprocess_frame(frame, quality, mode="off")
        assert isinstance(result, PreprocessedFrame)
        assert result.preprocessing_mode == "off"
        assert result.skip_detection is False
        np.testing.assert_array_equal(result.frame, frame)

    def test_unusable_always_skip(self):
        """UNUSABLE quality → skip_detection=True regardless of mode."""
        frame = make_dark_frame()
        quality = make_quality(QualityClass.UNUSABLE)
        for mode in ("off", "clahe", "clahe_gamma", "auto"):
            result = preprocess_frame(frame, quality, mode=mode)
            assert result.skip_detection is True, f"Expected skip with mode={mode}"

    def test_result_has_all_fields(self):
        """PreprocessedFrame has all required fields."""
        frame = make_normal_frame()
        quality = make_quality(QualityClass.NORMAL)
        result = preprocess_frame(frame, quality, mode="off")
        assert hasattr(result, "frame")
        assert hasattr(result, "preprocessing_mode")
        assert hasattr(result, "skip_detection")
        assert hasattr(result, "quality_class")
        assert hasattr(result, "original_mean_lum")
        assert hasattr(result, "enhanced_mean_lum")

    def test_output_shape_unchanged_clahe(self):
        """CLAHE output has same shape as input."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_dark_frame(200, 300)
        quality = make_quality(QualityClass.LOW_LIGHT, mean_lum=45.0, preprocessing="clahe")
        result = preprocess_frame(frame, quality, mode="clahe")
        assert result.frame.shape == frame.shape

    def test_output_shape_unchanged_clahe_gamma(self):
        """CLAHE+gamma output has same shape as input."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_dark_frame(200, 300)
        quality = make_quality(QualityClass.VERY_LOW_LIGHT, mean_lum=20.0, preprocessing="clahe_gamma")
        result = preprocess_frame(frame, quality, mode="clahe_gamma")
        assert result.frame.shape == frame.shape

    def test_output_dtype_uint8(self):
        """Output frame must be uint8 (required by YOLO)."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_dark_frame()
        quality = make_quality(QualityClass.LOW_LIGHT, mean_lum=45.0, preprocessing="clahe")
        result = preprocess_frame(frame, quality, mode="clahe")
        assert result.frame.dtype == np.uint8


# ── mode='auto' tests ──────────────────────────────────────────────────────

class TestAutoMode:

    def test_auto_normal_no_preprocessing(self):
        """NORMAL quality + auto → mode should be 'off'."""
        frame = make_normal_frame()
        quality = make_quality(QualityClass.NORMAL)
        result = preprocess_frame(frame, quality, mode="auto")
        assert result.preprocessing_mode == "off"
        assert result.skip_detection is False

    def test_auto_low_light_applies_clahe(self):
        """LOW_LIGHT quality + auto → mode should be 'clahe'."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_dark_frame()
        quality = make_quality(QualityClass.LOW_LIGHT, mean_lum=45.0, preprocessing="clahe")
        result = preprocess_frame(frame, quality, mode="auto")
        assert result.preprocessing_mode == "clahe"
        assert result.skip_detection is False

    def test_auto_very_low_light_applies_clahe_gamma(self):
        """VERY_LOW_LIGHT quality + auto → mode should be 'clahe_gamma'."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_dark_frame()
        quality = make_quality(QualityClass.VERY_LOW_LIGHT, mean_lum=20.0, preprocessing="clahe_gamma")
        result = preprocess_frame(frame, quality, mode="auto")
        assert result.preprocessing_mode == "clahe_gamma"
        assert result.skip_detection is False

    def test_auto_unusable_skips(self):
        """UNUSABLE quality + auto → skip_detection=True."""
        frame = make_dark_frame()
        quality = make_quality(QualityClass.UNUSABLE, mean_lum=2.0)
        result = preprocess_frame(frame, quality, mode="auto")
        assert result.skip_detection is True


# ── Enhancement effectiveness tests ───────────────────────────────────────

class TestEnhancementEffectiveness:

    def test_gamma_brightens_dark_frame(self):
        """Gamma correction (gamma > 1) should increase mean luminance."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_dark_frame()
        enhanced = _apply_gamma(frame, gamma=2.0)
        import cv2
        orig_mean = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()
        enh_mean = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY).mean()
        assert enh_mean > orig_mean, f"Gamma should brighten: {orig_mean:.1f} → {enh_mean:.1f}"

    def test_gamma_shape_preserved(self):
        """Gamma output shape must equal input shape."""
        frame = make_dark_frame(50, 75)
        enhanced = _apply_gamma(frame, gamma=1.5)
        assert enhanced.shape == frame.shape
        assert enhanced.dtype == np.uint8

    def test_clahe_improves_contrast_on_dark_uniform(self):
        """CLAHE on a very dark uniform frame should increase std (contrast)."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        # Near-uniform dark frame with slight noise
        rng = np.random.default_rng(0)
        frame = rng.integers(18, 22, (100, 100, 3), dtype=np.uint8)  # very low contrast
        enhanced = _apply_clahe(frame, clip_limit=3.0, tile_size=(8, 8))
        import cv2
        orig_std = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(float).std()
        enh_std  = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY).astype(float).std()
        assert enh_std >= orig_std, f"CLAHE should improve contrast: {orig_std:.2f} → {enh_std:.2f}"


# ── preprocess_frame_from_path tests ──────────────────────────────────────

class TestPreprocessFrameFromPath:

    def test_missing_file_returns_none(self):
        """Missing file path → returns None (no exception)."""
        result = preprocess_frame_from_path("/nonexistent/path/frame.jpg")
        assert result is None

    def test_valid_file(self, tmp_path):
        """Valid JPEG file → returns PreprocessedFrame."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_normal_frame(100, 100)
        path = str(tmp_path / "frame.jpg")
        import cv2
        cv2.imwrite(path, frame)
        result = preprocess_frame_from_path(path, frame_number=3, timestamp_ms=300.0)
        assert result is not None
        assert isinstance(result, PreprocessedFrame)
        assert result.frame.shape == frame.shape


# ── Edge cases ─────────────────────────────────────────────────────────────

class TestEdgeCases:

    def test_none_frame_input(self):
        """None frame input returns skip_detection=True."""
        quality = make_quality(QualityClass.NORMAL)
        result = preprocess_frame(None, quality, mode="off")
        assert result.skip_detection is True

    def test_empty_frame_input(self):
        """Empty array input returns skip_detection=True."""
        quality = make_quality(QualityClass.NORMAL)
        result = preprocess_frame(np.array([]), quality, mode="off")
        assert result.skip_detection is True

    def test_large_frame_does_not_crash(self):
        """Full HD frame (1920×1080) processes without error."""
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        rng = np.random.default_rng(99)
        frame = rng.integers(80, 200, (1080, 1920, 3), dtype=np.uint8)
        quality = make_quality(QualityClass.LOW_LIGHT, mean_lum=50.0, preprocessing="clahe")
        result = preprocess_frame(frame, quality, mode="clahe")
        assert result.frame.shape == (1080, 1920, 3)
