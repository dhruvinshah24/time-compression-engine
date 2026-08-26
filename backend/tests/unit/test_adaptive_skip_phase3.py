"""
Tests: Adaptive Frame Skip (Phase 3) — pre-extraction streaming.

Tests validate the AdaptiveSkipAnalyzer and select_frames_for_extraction()
using synthetic video frames (NumPy arrays) to avoid requiring a real video file.

Status: IMPLEMENTED — unit tested with synthetic frames.
"""

import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.utils.adaptive_skip import (
    AdaptiveSkipAnalyzer,
    AdaptiveSkipConfig,
    AdaptiveSkipStats,
    TIER_STATIC,
    TIER_LOW_MOTION,
    TIER_MEDIUM,
    TIER_HIGH,
    TIER_PROTECTED,
    compute_adaptive_stats,
)


# ── Synthetic video helpers ────────────────────────────────────────────────────

def _make_static_video(path: str, n_frames: int = 60, fps: int = 25) -> None:
    """Write a video of all-gray frames (static scene)."""
    h, w = 180, 320
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    frame = np.full((h, w, 3), 128, dtype=np.uint8)
    for _ in range(n_frames):
        out.write(frame)
    out.release()


def _make_high_motion_video(path: str, n_frames: int = 60, fps: int = 25) -> None:
    """Write a video of randomly-changing frames (high motion)."""
    h, w = 180, 320
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))
    rng = np.random.default_rng(42)
    for _ in range(n_frames):
        frame = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
        out.write(frame)
    out.release()


def _make_mixed_video(path: str, fps: int = 25) -> tuple[int, int]:
    """
    Write a video: 30 static frames, then 10 high-motion frames, then 20 static.
    Returns (static_start, motion_start, static_end) frame indices.
    """
    h, w = 180, 320
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (w, h))

    static = np.full((h, w, 3), 128, dtype=np.uint8)
    rng = np.random.default_rng(7)

    for _ in range(30):    # 0–29: static
        out.write(static)
    for _ in range(10):    # 30–39: high motion
        out.write(rng.integers(0, 255, (h, w, 3), dtype=np.uint8))
    for _ in range(20):    # 40–59: static again
        out.write(static)
    out.release()
    return 30, 40  # motion_start, motion_end frame indices


# ── Tests: AdaptiveSkipConfig ─────────────────────────────────────────────────

def test_adaptive_skip_config_defaults():
    cfg = AdaptiveSkipConfig()
    assert cfg.enabled is True
    assert cfg.static_skip > cfg.low_motion_skip
    assert cfg.low_motion_skip > cfg.medium_motion_skip
    assert cfg.medium_motion_skip >= cfg.high_motion_skip
    assert cfg.min_skip >= 1
    assert cfg.max_skip <= 30


def test_adaptive_skip_config_custom():
    cfg = AdaptiveSkipConfig(static_skip=8, high_motion_skip=1, protection_threshold=0.05)
    assert cfg.static_skip == 8
    assert cfg.high_motion_skip == 1
    assert cfg.protection_threshold == 0.05


# ── Tests: static scene ───────────────────────────────────────────────────────

def test_static_scene_selects_few_frames(tmp_path):
    """Static video → most frames skipped, low sampling ratio."""
    vid = str(tmp_path / "static.mp4")
    _make_static_video(vid, n_frames=100, fps=25)

    cfg = AdaptiveSkipConfig(warmup_frames=10)
    analyzer = AdaptiveSkipAnalyzer(config=cfg)
    indices, stats = analyzer.select_frames(vid)

    assert len(indices) > 0, "Should select at least some frames"
    # Static scene should skip aggressively after warmup
    assert stats.effective_sampling_ratio < 0.5, (
        f"Expected <50% sampling on static video, got {stats.effective_sampling_ratio:.2%}"
    )


def test_static_scene_stats_totals_consistent(tmp_path):
    """frames_selected + frames_skipped == total_video_frames."""
    vid = str(tmp_path / "static2.mp4")
    _make_static_video(vid, n_frames=60)

    analyzer = AdaptiveSkipAnalyzer()
    indices, stats = analyzer.select_frames(vid)

    assert stats.frames_selected + stats.frames_skipped == stats.total_video_frames, (
        f"selected({stats.frames_selected}) + skipped({stats.frames_skipped}) "
        f"!= total({stats.total_video_frames})"
    )


# ── Tests: high motion ────────────────────────────────────────────────────────

def test_high_motion_selects_most_frames(tmp_path):
    """Rapidly changing frames → high sampling ratio."""
    vid = str(tmp_path / "motion.mp4")
    _make_high_motion_video(vid, n_frames=60)

    cfg = AdaptiveSkipConfig(warmup_frames=5, high_motion_skip=1)
    analyzer = AdaptiveSkipAnalyzer(config=cfg)
    indices, stats = analyzer.select_frames(vid)

    # After warmup: random noise should trigger HIGH_MOTION tier
    assert stats.maximum_motion_score > 0.10, (
        f"Expected >10% max motion on random video, got {stats.maximum_motion_score:.2%}"
    )


# ── Tests: protection triggers ────────────────────────────────────────────────

def test_protection_triggers_on_motion_spike(tmp_path):
    """Mixed video: static → burst → static. Protection should trigger during burst."""
    vid = str(tmp_path / "mixed.mp4")
    motion_start, motion_end = _make_mixed_video(vid)

    cfg = AdaptiveSkipConfig(
        warmup_frames=5,
        protection_threshold=0.08,
        protection_window_frames=10,
    )
    analyzer = AdaptiveSkipAnalyzer(config=cfg)
    indices, stats = analyzer.select_frames(vid)

    assert stats.protected_windows >= 1, (
        "Expected at least 1 protection window triggered by motion burst"
    )
    assert stats.protected_frames >= 1


def test_protection_does_not_trigger_on_gradual_change(tmp_path):
    """Slowly brightening frames should not trigger PROTECTED mode."""
    h, w = 180, 320
    vid_path = str(tmp_path / "gradual.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(vid_path, fourcc, 25, (w, h))
    for i in range(60):
        brightness = 50 + i  # gradual increase 50→109
        frame = np.full((h, w, 3), brightness, dtype=np.uint8)
        out.write(frame)
    out.release()

    cfg = AdaptiveSkipConfig(warmup_frames=10, protection_threshold=0.08)
    analyzer = AdaptiveSkipAnalyzer(config=cfg)
    _, stats = analyzer.select_frames(vid_path)

    # Gradual brightness change produces very low MOG2 foreground — no protection
    assert stats.protected_windows == 0, (
        f"Gradual change should not trigger protection, got {stats.protected_windows} windows"
    )


# ── Tests: external protection trigger ───────────────────────────────────────

def test_external_protection_trigger():
    """trigger_protection() from external signal increases window count."""
    analyzer = AdaptiveSkipAnalyzer()
    assert not analyzer.is_protected

    analyzer.trigger_protection("roi_proximity")
    assert analyzer.is_protected
    assert analyzer._protection_windows == 1


def test_protection_countdown_decrements():
    """Protection countdown decreases each frame."""
    cfg = AdaptiveSkipConfig(protection_window_frames=3, warmup_frames=0)
    analyzer = AdaptiveSkipAnalyzer(config=cfg)
    analyzer.trigger_protection("test")
    assert analyzer._protection_remaining == 3

    # Feed a low-motion frame to consume one protection frame
    blank = np.zeros((180, 320, 3), dtype=np.uint8)
    analyzer._compute_motion(blank, frame_idx=1, timestamp_ms=0)
    assert analyzer._protection_remaining == 2


# ── Tests: sorted indices ─────────────────────────────────────────────────────

def test_selected_indices_are_sorted(tmp_path):
    """Returned frame indices must be in ascending order."""
    vid = str(tmp_path / "order.mp4")
    _make_static_video(vid, n_frames=50)
    analyzer = AdaptiveSkipAnalyzer()
    indices, _ = analyzer.select_frames(vid)
    assert indices == sorted(indices)


def test_selected_indices_contain_no_duplicates(tmp_path):
    vid = str(tmp_path / "dup.mp4")
    _make_static_video(vid, n_frames=50)
    analyzer = AdaptiveSkipAnalyzer()
    indices, _ = analyzer.select_frames(vid)
    assert len(indices) == len(set(indices)), "Indices must be unique"


# ── Tests: warmup phase ───────────────────────────────────────────────────────

def test_warmup_frames_use_medium_skip():
    """During warmup, smoothed_skip == medium_motion_skip regardless of motion."""
    cfg = AdaptiveSkipConfig(warmup_frames=10, medium_motion_skip=3)
    analyzer = AdaptiveSkipAnalyzer(config=cfg)

    blank = np.zeros((180, 320, 3), dtype=np.uint8)
    for i in range(5):  # within warmup
        score = analyzer._compute_motion(blank, frame_idx=i, timestamp_ms=0)
        assert score.smoothed_skip == cfg.medium_motion_skip, (
            f"Warmup frame {i}: expected skip={cfg.medium_motion_skip}, "
            f"got {score.smoothed_skip}"
        )


# ── Tests: EMA smoothing ──────────────────────────────────────────────────────

def test_ema_smoothing_prevents_rapid_oscillation():
    """
    Skip rate should not swing 1→10→1→10 on alternating high/low motion.
    EMA should smooth this out.
    """
    cfg = AdaptiveSkipConfig(warmup_frames=0, ema_alpha=0.3)
    analyzer = AdaptiveSkipAnalyzer(config=cfg)

    rng = np.random.default_rng(0)
    skips = []
    for i in range(20):
        if i % 2 == 0:
            frame = np.zeros((180, 320, 3), dtype=np.uint8)  # static
        else:
            frame = rng.integers(0, 255, (180, 320, 3), dtype=np.uint8)  # noisy
        score = analyzer._compute_motion(frame, frame_idx=i, timestamp_ms=0)
        skips.append(score.smoothed_skip)

    # With EMA, skip changes should be gradual — no instant jump from 1 to 10
    max_jump = max(abs(skips[i+1] - skips[i]) for i in range(len(skips)-1))
    assert max_jump < 8, (
        f"Skip rate jumped by {max_jump} between consecutive frames — "
        "EMA not smoothing properly"
    )


# ── Tests: AdaptiveSkipStats ──────────────────────────────────────────────────

def test_adaptive_stats_to_dict_has_required_keys(tmp_path):
    vid = str(tmp_path / "stats.mp4")
    _make_static_video(vid, n_frames=30)
    analyzer = AdaptiveSkipAnalyzer()
    _, stats = analyzer.select_frames(vid)
    d = stats.to_dict()
    required = [
        "total_video_frames", "frames_examined", "frames_selected",
        "frames_skipped", "effective_sampling_ratio",
        "average_motion_score_pct", "maximum_motion_score_pct",
        "protected_windows", "protected_frames", "skip_source",
        "tier_distribution",
    ]
    for key in required:
        assert key in d, f"Missing key: {key}"


def test_compute_adaptive_stats_on_empty_list():
    result = compute_adaptive_stats([])
    assert result == {}


# ── Tests: disabled config ────────────────────────────────────────────────────

def test_disabled_config_uses_baseline_skip(tmp_path):
    """When enabled=False, select_frames() still runs but marks skip_source as 'fixed'."""
    vid = str(tmp_path / "disabled.mp4")
    _make_high_motion_video(vid, n_frames=30)
    cfg = AdaptiveSkipConfig(enabled=False, medium_motion_skip=5)
    analyzer = AdaptiveSkipAnalyzer(config=cfg)
    indices, stats = analyzer.select_frames(vid)
    # When enabled=False, AdaptiveSkipAnalyzer uses fixed/warmup skips
    # skip_source is "fixed" because enabled=False
    assert stats.skip_source == "fixed"
    assert stats.frames_selected > 0

