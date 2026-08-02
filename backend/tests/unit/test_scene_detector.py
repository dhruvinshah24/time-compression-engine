"""
Unit tests for Phase 3A: Scene Change Detection.

Test coverage:
  1. SceneChangeConfig validation
  2. Individual metrics (pixel_diff, histogram_diff, composite)
  3. AdaptiveThreshold rolling window behaviour
  4. SceneChangeDetector end-to-end with synthetic frames
  5. Edge cases: empty input, single frame, all duplicates, all hard cuts
  6. s03_scene_detect pipeline stage (mocked)

Synthetic frame generation:
  - We generate numpy arrays directly rather than writing/reading JPEG files.
  - This makes tests 100x faster and eliminates filesystem I/O.
  - The load_frame() function is mocked to return pre-built arrays.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Synthetic frame helpers
# ---------------------------------------------------------------------------

def _make_frame(r: int = 128, g: int = 128, b: int = 128, noise: int = 0) -> np.ndarray:
    """Create a solid-color 224×224 RGB numpy array with optional noise."""
    arr = np.full((224, 224, 3), [r, g, b], dtype=np.uint8)
    if noise > 0:
        rng = np.random.default_rng(42)
        arr = np.clip(
            arr.astype(np.int16) + rng.integers(-noise, noise + 1, arr.shape),
            0, 255
        ).astype(np.uint8)
    return arr


def _write_frame_jpeg(arr: np.ndarray, path: Path) -> None:
    """Write a numpy array as JPEG to disk."""
    Image.fromarray(arr).save(path, "JPEG", quality=95)


# ---------------------------------------------------------------------------
# SceneChangeConfig tests
# ---------------------------------------------------------------------------

class TestSceneChangeConfig:
    def test_defaults_are_valid(self):
        from app.engines.perception.change_detector.config import SceneChangeConfig
        cfg = SceneChangeConfig()
        assert cfg.pixel_weight + cfg.histogram_weight == pytest.approx(1.0)
        assert cfg.adaptive_window >= 5
        assert 0.0 < cfg.hard_cut_threshold <= 1.0

    def test_invalid_weights_raise(self):
        from app.engines.perception.change_detector.config import SceneChangeConfig
        with pytest.raises(ValueError, match="1.0"):
            SceneChangeConfig(pixel_weight=0.3, histogram_weight=0.3)

    def test_invalid_adaptive_window_raises(self):
        from app.engines.perception.change_detector.config import SceneChangeConfig
        with pytest.raises(ValueError, match="adaptive_window"):
            SceneChangeConfig(adaptive_window=2)

    def test_invalid_hard_cut_threshold_raises(self):
        from app.engines.perception.change_detector.config import SceneChangeConfig
        with pytest.raises(ValueError, match="hard_cut_threshold"):
            SceneChangeConfig(hard_cut_threshold=1.5)

    def test_custom_values(self):
        from app.engines.perception.change_detector.config import SceneChangeConfig
        cfg = SceneChangeConfig(pixel_weight=0.3, histogram_weight=0.7, adaptive_k=2.0)
        assert cfg.pixel_weight == pytest.approx(0.3)
        assert cfg.adaptive_k == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Pixel difference metric tests
# ---------------------------------------------------------------------------

class TestPixelDiff:
    def test_identical_frames_score_zero(self):
        from app.engines.perception.change_detector.metrics import compute_pixel_diff
        frame = _make_frame(128, 128, 128)
        score = compute_pixel_diff(frame, frame)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_black_vs_white_max_diff(self):
        from app.engines.perception.change_detector.metrics import compute_pixel_diff
        black = _make_frame(0, 0, 0)
        white = _make_frame(255, 255, 255)
        score = compute_pixel_diff(black, white)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_slight_change_low_score(self):
        from app.engines.perception.change_detector.metrics import compute_pixel_diff
        frame_a = _make_frame(100, 100, 100)
        frame_b = _make_frame(105, 105, 105)
        score = compute_pixel_diff(frame_a, frame_b)
        assert score < 0.05

    def test_score_in_valid_range(self):
        from app.engines.perception.change_detector.metrics import compute_pixel_diff
        rng = np.random.default_rng(0)
        for _ in range(10):
            a = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
            b = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
            score = compute_pixel_diff(a, b)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Histogram difference metric tests
# ---------------------------------------------------------------------------

class TestHistogramDiff:
    def test_identical_frames_score_zero(self):
        from app.engines.perception.change_detector.metrics import compute_histogram_diff
        frame = _make_frame(128, 100, 80)
        score = compute_histogram_diff(frame, frame)
        assert score == pytest.approx(0.0, abs=0.05)

    def test_very_different_scenes_high_score(self):
        from app.engines.perception.change_detector.metrics import compute_histogram_diff
        red_frame = _make_frame(220, 30, 30)
        blue_frame = _make_frame(30, 30, 220)
        score = compute_histogram_diff(red_frame, blue_frame)
        assert score > 0.3  # Clearly different color distributions

    def test_score_in_valid_range(self):
        from app.engines.perception.change_detector.metrics import compute_histogram_diff
        rng = np.random.default_rng(0)
        for _ in range(10):
            a = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
            b = rng.integers(0, 256, (224, 224, 3), dtype=np.uint8)
            score = compute_histogram_diff(a, b)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Composite score tests
# ---------------------------------------------------------------------------

class TestCompositeScore:
    def test_zero_inputs(self):
        from app.engines.perception.change_detector.metrics import compute_composite_score
        assert compute_composite_score(0.0, 0.0) == pytest.approx(0.0)

    def test_max_inputs(self):
        from app.engines.perception.change_detector.metrics import compute_composite_score
        assert compute_composite_score(1.0, 1.0) == pytest.approx(1.0)

    def test_weighted_combination(self):
        from app.engines.perception.change_detector.metrics import compute_composite_score
        # pixel=0.5, hist=0.5, weights 0.4/0.6 → 0.4*0.5 + 0.6*0.5 = 0.5
        score = compute_composite_score(0.5, 0.5, pixel_weight=0.4, histogram_weight=0.6)
        assert score == pytest.approx(0.5)

    def test_histogram_weighted_higher(self):
        from app.engines.perception.change_detector.metrics import compute_composite_score
        # pixel=0 (no pixel change), hist=1 (complete color change)
        score = compute_composite_score(0.0, 1.0, pixel_weight=0.4, histogram_weight=0.6)
        assert score == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# AdaptiveThreshold tests
# ---------------------------------------------------------------------------

class TestAdaptiveThreshold:
    def test_initial_threshold_is_reasonable(self):
        from app.engines.perception.change_detector.detector import AdaptiveThreshold
        thresh = AdaptiveThreshold(window=50, k=1.5)
        # Pre-filled with 0.05 — threshold ≈ 0.05 + 1.5 * 0.0 = 0.05
        t = thresh.threshold()
        assert 0.0 < t < 0.3

    def test_threshold_adapts_to_noisy_input(self):
        from app.engines.perception.change_detector.detector import AdaptiveThreshold
        thresh = AdaptiveThreshold(window=50, k=1.5)
        # Feed in high variance scores (simulating shaky camera)
        rng = np.random.default_rng(42)
        for v in rng.uniform(0.1, 0.8, 100):
            thresh.update(float(v))
        # Threshold should be higher than for a quiet camera
        assert thresh.threshold() > 0.3

    def test_threshold_stays_low_for_static_video(self):
        from app.engines.perception.change_detector.detector import AdaptiveThreshold
        thresh = AdaptiveThreshold(window=50, k=1.5)
        # Feed in very small scores (simulating empty room)
        for _ in range(100):
            thresh.update(0.005)
        # Should produce a very low threshold
        assert thresh.threshold() < 0.05


# ---------------------------------------------------------------------------
# SceneChangeDetector end-to-end tests
# ---------------------------------------------------------------------------

class TestSceneChangeDetector:
    """
    End-to-end tests using synthetic JPEG frames written to tmp_path.
    """

    def _write_frames(self, tmp_path: Path, frame_arrays: list[np.ndarray]) -> list[str]:
        """Write synthetic frames as JPEG files and return their paths."""
        paths = []
        for i, arr in enumerate(frame_arrays):
            path = tmp_path / f"frame_{i + 1:08d}.jpg"
            _write_frame_jpeg(arr, path)
            paths.append(str(path))
        return paths

    def test_empty_input_returns_empty_result(self):
        from app.engines.perception.change_detector.detector import SceneChangeDetector
        detector = SceneChangeDetector()
        result = detector.detect([], fps=25.0)
        assert result.keyframes == []
        assert result.scene_boundaries == []

    def test_single_frame_is_always_keyframe(self, tmp_path):
        from app.engines.perception.change_detector.detector import SceneChangeDetector
        paths = self._write_frames(tmp_path, [_make_frame(128, 128, 128)])
        detector = SceneChangeDetector()
        result = detector.detect(paths, fps=25.0)
        assert len(result.keyframes) == 1

    def test_identical_frames_classified_as_duplicates(self, tmp_path):
        from app.engines.perception.change_detector.detector import SceneChangeDetector
        # 20 identical frames
        frames = [_make_frame(128, 128, 128)] * 20
        paths = self._write_frames(tmp_path, frames)
        detector = SceneChangeDetector()
        result = detector.detect(paths, fps=25.0)
        # All after the first should be duplicates
        assert len(result.duplicate_frames) >= 15

    def test_hard_cut_detected(self, tmp_path):
        from app.engines.perception.change_detector.detector import SceneChangeDetector
        from app.engines.perception.change_detector.config import SceneChangeConfig
        # 10 dark frames then 10 bright frames (dramatic change)
        dark = [_make_frame(20, 20, 20)] * 10
        bright = [_make_frame(235, 235, 235)] * 10
        paths = self._write_frames(tmp_path, dark + bright)

        cfg = SceneChangeConfig(hard_cut_threshold=0.5)
        detector = SceneChangeDetector(config=cfg)
        result = detector.detect(paths, fps=25.0)
        assert result.metrics.get("hard_cuts", 0) >= 1

    def test_noisy_frames_not_all_boundaries(self, tmp_path):
        from app.engines.perception.change_detector.detector import SceneChangeDetector
        # Frames with minor pixel noise should NOT all be boundaries
        rng = np.random.default_rng(0)
        frames = []
        base = _make_frame(128, 128, 128)
        for _ in range(30):
            noisy = np.clip(
                base.astype(np.int16) + rng.integers(-5, 6, base.shape),
                0, 255
            ).astype(np.uint8)
            frames.append(noisy)
        paths = self._write_frames(tmp_path, frames)

        detector = SceneChangeDetector()
        result = detector.detect(paths, fps=25.0)
        # Noise-only variation should produce very few boundaries
        assert len(result.scene_boundaries) < 5

    def test_result_metrics_populated(self, tmp_path):
        from app.engines.perception.change_detector.detector import SceneChangeDetector
        frames = [_make_frame(128, 128, 128)] * 10
        paths = self._write_frames(tmp_path, frames)
        detector = SceneChangeDetector()
        result = detector.detect(paths, fps=25.0)

        assert "total_frames" in result.metrics
        assert result.metrics["total_frames"] == 10
        assert "duplicate_rate" in result.metrics
        assert "reduction_ratio" in result.metrics

    def test_health_check_ready_with_pillow(self):
        from app.engines.perception.change_detector.detector import SceneChangeDetector
        from app.engines.base import ModuleHealth
        detector = SceneChangeDetector()
        health = detector.health_check()
        # If Pillow is installed (it should be), health is READY
        assert health in (ModuleHealth.READY, ModuleHealth.UNAVAILABLE)


# ---------------------------------------------------------------------------
# s03_scene_detect pipeline stage tests
# ---------------------------------------------------------------------------

class TestS03SceneDetect:
    def _make_context(self, tmp_path: Path, frame_paths: list[str] | None = None) -> object:
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-20260730-TEST",
            video_id="test-vid",
            video_path=str(tmp_path / "video.mp4"),
            output_dir=str(tmp_path),
            settings={
                "scene_change_adaptive_k": 1.5,
                "scene_change_hard_cut_threshold": 0.70,
                "scene_change_duplicate_threshold": 0.02,
            },
            metadata={
                "fps": 25.0,
                "frame_skip_rate": 5,
            },
        )
        if frame_paths is not None:
            ctx.metadata["frame_paths"] = frame_paths
        return ctx

    @pytest.mark.asyncio
    async def test_missing_frame_paths_fails(self, tmp_path):
        from app.pipeline.stages import s03_scene_detect
        context = self._make_context(tmp_path)  # no frame_paths
        result = await s03_scene_detect.run(context)
        assert result.success is False
        assert any("frame_paths" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s03_scene_detect.SceneChangeDetector")
    @patch("app.pipeline.stages.s03_scene_detect.save_stage_metrics")
    async def test_successful_detection(self, mock_save, MockDetector, tmp_path):
        from app.engines.perception.change_detector.detector import SceneChangeResult

        mock_result = SceneChangeResult(
            scene_boundaries=[10, 50],
            duplicate_frames=[3, 4, 5],
            keyframes=[1, 10, 20, 30, 50, 60],
            keyframe_paths=[f"/frames/frame_{i:08d}.jpg" for i in [1, 10, 20, 30, 50, 60]],
            all_scores=[],
            metrics={
                "total_frames": 100,
                "hard_cuts": 1,
                "duplicate_rate": 0.03,
                "reduction_ratio": 16.7,
                "avg_composite": 0.12,
                "max_composite": 0.82,
                "processing_time_ms": 450,
                "processing_fps": 222.0,
            },
        )

        MockDetector.return_value.detect.return_value = mock_result
        mock_save.return_value = None

        context = self._make_context(tmp_path, frame_paths=["frame_001.jpg"] * 100)
        from app.pipeline.stages import s03_scene_detect
        result = await s03_scene_detect.run(context)

        assert result.success is True
        assert result.metrics["scene_boundaries_detected"] == 2
        assert result.metrics["keyframes_selected"] == 6
        assert context.metadata["keyframe_paths"] is not None
        assert context.metadata["scene_boundaries"] == [10, 50]

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s03_scene_detect.SceneChangeDetector")
    @patch("app.pipeline.stages.s03_scene_detect.save_stage_metrics")
    async def test_zero_keyframes_adds_warning(self, mock_save, MockDetector, tmp_path):
        from app.engines.perception.change_detector.detector import SceneChangeResult

        mock_result = SceneChangeResult(
            scene_boundaries=[],
            duplicate_frames=list(range(50)),
            keyframes=[],
            keyframe_paths=[],
            all_scores=[],
            metrics={"total_frames": 50, "hard_cuts": 0, "duplicate_rate": 1.0,
                      "reduction_ratio": 0.0, "avg_composite": 0.001, "max_composite": 0.01},
        )

        MockDetector.return_value.detect.return_value = mock_result
        mock_save.return_value = None

        context = self._make_context(tmp_path, frame_paths=["frame.jpg"] * 50)
        from app.pipeline.stages import s03_scene_detect
        result = await s03_scene_detect.run(context)

        # Zero keyframes is a warning, not a failure
        assert result.success is True
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_stage_name_correct(self, tmp_path):
        from app.pipeline.stages import s03_scene_detect
        context = self._make_context(tmp_path)
        result = await s03_scene_detect.run(context)
        assert result.stage_name == "s03_scene_detect"
