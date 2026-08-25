"""
Unit tests for quality_analyzer.py — TCE Accuracy Overhaul v1.0.1.

No GPU required. No real video files required.
"""

import json
import numpy as np
import pytest

from app.utils.quality_analyzer import (
    QualityClass,
    QualityThresholds,
    FrameQuality,
    VideoQualityReport,
    analyze_frame,
    analyze_frame_from_path,
    analyze_video_quality,
    DEFAULT_THRESHOLDS,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def make_frame(r: int, g: int, b: int, h: int = 100, w: int = 100) -> np.ndarray:
    """Create a solid-color BGR frame."""
    return np.full((h, w, 3), [b, g, r], dtype=np.uint8)


def make_noisy_frame(mean: int = 150, h: int = 100, w: int = 100, seed: int = 42) -> np.ndarray:
    """Create a noisy BGR frame around a given mean luminance."""
    rng = np.random.default_rng(seed)
    low = max(0, mean - 30)
    high = min(255, mean + 30)
    return rng.integers(low, high + 1, (h, w, 3), dtype=np.uint8)


# ── analyze_frame tests ────────────────────────────────────────────────────

class TestAnalyzeFrame:

    def test_normal_noisy_frame(self):
        """A well-lit noisy frame should be classified NORMAL."""
        frame = make_noisy_frame(mean=150)
        result = analyze_frame(frame)
        assert result.quality_class == QualityClass.NORMAL
        assert result.recommended_preprocessing == "off"
        assert result.skip_detection_recommended is False

    def test_all_black_frame_is_unusable(self):
        """A black frame is below the usable luminance threshold."""
        frame = make_frame(0, 0, 0)
        result = analyze_frame(frame)
        assert result.quality_class == QualityClass.UNUSABLE
        assert result.mean_luminance < 5.0
        assert result.skip_detection_recommended is True

    def test_very_dark_noisy_frame_is_very_low_light_or_worse(self):
        """A very dark noisy frame → VERY_LOW_LIGHT or UNUSABLE."""
        frame = make_noisy_frame(mean=20)
        result = analyze_frame(frame)
        assert result.quality_class in (QualityClass.VERY_LOW_LIGHT, QualityClass.UNUSABLE)

    def test_dim_noisy_frame_classified_correctly(self):
        """Frame with mean ~27 and many dark pixels should be LOW_LIGHT or darker.
        
        LOW_LIGHT requires mean_lum < 60 AND dark_pixel_ratio >= 0.30.
        Pixels in [5,50]: mean≈27, ~50% of pixels fall below 30 → dark_pixel_ratio≈0.5.
        """
        rng = np.random.default_rng(55)
        frame = rng.integers(5, 50, (100, 100, 3), dtype=np.uint8)
        result = analyze_frame(frame)
        # Mean≈27 < 30 → triggers very_low_light if dark_ratio >= 0.60
        # OR falls to low_light if mean < 60 and dark_ratio >= 0.30
        assert result.quality_class in (
            QualityClass.LOW_LIGHT, QualityClass.VERY_LOW_LIGHT, QualityClass.UNUSABLE
        )


    def test_uniform_frame_has_low_blur(self):
        """A uniform solid-color frame has near-zero Laplacian variance."""
        frame = make_frame(100, 100, 100)
        result = analyze_frame(frame)
        assert result.blur_score < 5.0

    def test_noisy_frame_has_high_blur(self):
        """A noisy frame has high Laplacian variance."""
        frame = make_noisy_frame(mean=150)
        result = analyze_frame(frame)
        assert result.blur_score > 50.0

    def test_result_has_all_fields(self):
        """FrameQuality result includes all required fields."""
        frame = make_noisy_frame(mean=150)
        result = analyze_frame(frame, frame_number=5, timestamp_ms=500.0)
        assert result.frame_number == 5
        assert result.timestamp_ms == 500.0
        assert isinstance(result.mean_luminance, float)
        assert isinstance(result.luminance_std, float)
        assert isinstance(result.blur_score, float)
        assert isinstance(result.dark_pixel_ratio, float)
        assert isinstance(result.histogram_spread, float)
        assert isinstance(result.quality_class, QualityClass)
        assert result.recommended_preprocessing in ("off", "clahe", "clahe_gamma")

    def test_dark_pixel_ratio_all_black(self):
        """All-black frame → dark_pixel_ratio ≈ 1.0."""
        frame = make_frame(0, 0, 0)
        result = analyze_frame(frame)
        assert result.dark_pixel_ratio > 0.95

    def test_dark_pixel_ratio_all_white(self):
        """All-white frame → dark_pixel_ratio ≈ 0.0."""
        frame = make_frame(255, 255, 255)
        result = analyze_frame(frame)
        assert result.dark_pixel_ratio < 0.05

    def test_histogram_spread_uniform(self):
        """Uniform frame → very small p95-p5 spread."""
        frame = make_frame(100, 100, 100)
        result = analyze_frame(frame)
        assert result.histogram_spread < 5.0

    def test_histogram_spread_high_contrast(self):
        """Half-black, half-white frame → large histogram spread."""
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[:50, :] = 255
        result = analyze_frame(frame)
        assert result.histogram_spread > 100

    def test_empty_frame_returns_unusable(self):
        """Passing empty array returns UNUSABLE gracefully."""
        result = analyze_frame(np.array([]))
        assert result.quality_class == QualityClass.UNUSABLE

    def test_custom_thresholds_low_light(self):
        """Custom thresholds: set low_light_luminance=250, low_light_dark_ratio=0.0.
        
        This means ANY frame is classified LOW_LIGHT (as long as it's not UNUSABLE/VLL).
        Use a noisy frame (mean ~90) that won't trigger very_low_light.
        """
        rng = np.random.default_rng(9)
        # Range [60,120] → mean ≈ 90, dark_pixel_ratio ≈ 0.0 (no pixels < 30)
        frame = rng.integers(60, 120, (100, 100, 3), dtype=np.uint8)
        strict = QualityThresholds(
            unusable_blur_score=0.0,     # never unusable from blur
            unusable_luminance=0.0,      # never unusable from darkness
            very_low_light_luminance=5.0,    # very_low only if extremely dark
            very_low_light_dark_ratio=0.99,  # and almost all pixels dark
            low_light_luminance=250.0,   # anything under 250 luma is "low light"
            low_light_dark_ratio=0.0,    # even 0 dark pixels qualifies
        )
        result = analyze_frame(frame, thresholds=strict)
        # dark_pixel_ratio for [60,120] frame ≈ 0.0, which is > 0.0 threshold → LOW_LIGHT
        assert result.quality_class == QualityClass.LOW_LIGHT

    def test_normal_bright_noisy_frame(self):
        """A noisy frame with mean ~170 → NORMAL."""
        frame = make_noisy_frame(mean=170, seed=7)
        result = analyze_frame(frame)
        assert result.quality_class == QualityClass.NORMAL


# ── analyze_frame_from_path tests ─────────────────────────────────────────

class TestAnalyzeFrameFromPath:

    def test_missing_file_returns_none(self):
        result = analyze_frame_from_path("/nonexistent/path/frame.jpg")
        assert result is None

    def test_valid_jpeg_file(self, tmp_path):
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_noisy_frame(mean=150, h=200, w=200)
        path = str(tmp_path / "test_frame.jpg")
        cv2.imwrite(path, frame)
        result = analyze_frame_from_path(path, frame_number=1, timestamp_ms=100.0)
        assert result is not None
        assert result.frame_number == 1
        assert result.timestamp_ms == 100.0
        assert result.quality_class == QualityClass.NORMAL


# ── analyze_video_quality tests ────────────────────────────────────────────

class TestAnalyzeVideoQuality:

    def test_empty_frame_list_returns_defaults(self):
        report = analyze_video_quality([], [], [])
        assert isinstance(report, VideoQualityReport)
        assert report.total_frames == 0
        assert report.dominant_quality_class == QualityClass.NORMAL
        assert report.recommended_preprocessing == "off"

    def test_single_valid_frame(self, tmp_path):
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_noisy_frame(mean=150, h=100, w=100)
        path = str(tmp_path / "frame_001.jpg")
        cv2.imwrite(path, frame)
        report = analyze_video_quality([path], [1], [0.0])
        assert report.total_frames == 1
        assert report.dominant_quality_class == QualityClass.NORMAL
        assert report.mean_luminance > 50

    def test_all_dark_frames(self, tmp_path):
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        paths, nums, times = [], [], []
        for i in range(5):
            frame = make_noisy_frame(mean=18, seed=i)
            path = str(tmp_path / f"dark_{i}.jpg")
            cv2.imwrite(path, frame)
            paths.append(path)
            nums.append(i)
            times.append(float(i * 100))
        report = analyze_video_quality(paths, nums, times)
        total_dark = report.low_light_ratio + report.very_low_light_ratio + report.unusable_ratio
        assert total_dark > 0.5

    def test_summary_dict_is_serializable(self, tmp_path):
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        frame = make_noisy_frame(mean=150)
        path = str(tmp_path / "f.jpg")
        cv2.imwrite(path, frame)
        report = analyze_video_quality([path], [0], [0.0])
        d = report.summary_dict()
        json.dumps(d)  # Must not raise
        assert "dominant_quality_class" in d
        assert "recommended_preprocessing" in d

    def test_sample_rate_reduces_frames_analyzed(self, tmp_path):
        try:
            import cv2
        except ImportError:
            pytest.skip("OpenCV not installed")
        paths, nums, times = [], [], []
        for i in range(10):
            frame = make_noisy_frame(mean=150, seed=i)
            path = str(tmp_path / f"f_{i}.jpg")
            cv2.imwrite(path, frame)
            paths.append(path)
            nums.append(i)
            times.append(float(i * 40))
        report_full = analyze_video_quality(paths, nums, times, sample_rate=1)
        report_half = analyze_video_quality(paths, nums, times, sample_rate=2)
        assert len(report_full.per_frame) == 10
        assert len(report_half.per_frame) == 5


# ── skip_detection_recommended property ───────────────────────────────────

def test_frame_quality_skip_detection_unusable():
    fq = FrameQuality(
        frame_number=0, timestamp_ms=0.0,
        mean_luminance=1.0, luminance_std=0.0, blur_score=0.0,
        dark_pixel_ratio=1.0, histogram_spread=0.0,
        quality_class=QualityClass.UNUSABLE,
        recommended_preprocessing="off",
    )
    assert fq.skip_detection_recommended is True


def test_frame_quality_normal_no_skip():
    fq = FrameQuality(
        frame_number=0, timestamp_ms=0.0,
        mean_luminance=128.0, luminance_std=40.0, blur_score=200.0,
        dark_pixel_ratio=0.02, histogram_spread=180.0,
        quality_class=QualityClass.NORMAL,
        recommended_preprocessing="off",
    )
    assert fq.skip_detection_recommended is False


def test_low_light_no_skip():
    fq = FrameQuality(
        frame_number=0, timestamp_ms=0.0,
        mean_luminance=45.0, luminance_std=15.0, blur_score=80.0,
        dark_pixel_ratio=0.45, histogram_spread=80.0,
        quality_class=QualityClass.LOW_LIGHT,
        recommended_preprocessing="clahe",
    )
    assert fq.skip_detection_recommended is False
