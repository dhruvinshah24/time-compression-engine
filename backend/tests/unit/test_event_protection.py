"""
Tests: Event Protection Guard (Phase 3).
"""

import pytest
from unittest.mock import MagicMock, patch

from app.utils.adaptive_skip import AdaptiveSkipAnalyzer, AdaptiveSkipConfig, MotionScore, TIER_STATIC
from app.utils.event_protection import EventProtectionGuard


def _make_motion_score(frame_idx=0, motion=0.01, tier=TIER_STATIC, protected=False):
    return MotionScore(
        frame_index=frame_idx,
        timestamp_ms=0.0,
        motion_fraction=motion,
        motion_tier=tier,
        raw_skip=6,
        smoothed_skip=6,
        protected=protected,
    )


def test_guard_no_signals_no_protection():
    """Without external signals, guard does not trigger protection."""
    analyzer = AdaptiveSkipAnalyzer(AdaptiveSkipConfig(protection_window_frames=5))
    guard = EventProtectionGuard(analyzer)

    triggered = guard.check_and_protect(
        frame_idx=0,
        motion_score=_make_motion_score(),
        roi_proximity=False,
        track_count_changed=False,
        brightness_change=False,
    )
    assert triggered is False
    assert not guard.is_protected


def test_guard_roi_proximity_triggers_protection():
    analyzer = AdaptiveSkipAnalyzer(AdaptiveSkipConfig(protection_window_frames=5))
    guard = EventProtectionGuard(analyzer)

    triggered = guard.check_and_protect(
        frame_idx=10,
        motion_score=_make_motion_score(frame_idx=10),
        roi_proximity=True,
    )
    assert triggered is True
    assert guard.is_protected


def test_guard_track_count_change_triggers_protection():
    analyzer = AdaptiveSkipAnalyzer(AdaptiveSkipConfig(protection_window_frames=5))
    guard = EventProtectionGuard(analyzer)

    triggered = guard.check_and_protect(
        frame_idx=5,
        motion_score=_make_motion_score(frame_idx=5),
        track_count_changed=True,
    )
    assert triggered is True


def test_guard_brightness_change_triggers_protection():
    analyzer = AdaptiveSkipAnalyzer(AdaptiveSkipConfig(protection_window_frames=5))
    guard = EventProtectionGuard(analyzer)

    triggered = guard.check_and_protect(
        frame_idx=20,
        motion_score=_make_motion_score(frame_idx=20),
        brightness_change=True,
    )
    assert triggered is True


def test_guard_trigger_log_records_reason():
    analyzer = AdaptiveSkipAnalyzer(AdaptiveSkipConfig(protection_window_frames=3))
    guard = EventProtectionGuard(analyzer)

    guard.check_and_protect(0, _make_motion_score(0), roi_proximity=True)
    guard.check_and_protect(1, _make_motion_score(1), track_count_changed=True)

    log = guard.trigger_log
    assert len(log) == 2
    reasons = [t["reason"] for t in log]
    assert "roi_proximity" in reasons
    assert "new_track_appeared" in reasons


def test_guard_stats_dict_has_required_keys():
    analyzer = AdaptiveSkipAnalyzer()
    guard = EventProtectionGuard(analyzer)
    stats = guard.stats
    assert "external_triggers_total" in stats
    assert "triggers_by_reason" in stats
    assert "protection_currently_active" in stats


def test_guard_multiple_signals_same_frame():
    """Multiple signals in one frame should all be recorded."""
    analyzer = AdaptiveSkipAnalyzer(AdaptiveSkipConfig(protection_window_frames=10))
    guard = EventProtectionGuard(analyzer)

    guard.check_and_protect(
        frame_idx=0,
        motion_score=_make_motion_score(0),
        roi_proximity=True,
        track_count_changed=True,
        brightness_change=True,
    )
    log = guard.trigger_log
    assert len(log) == 3


def test_guard_stats_counts_by_reason():
    analyzer = AdaptiveSkipAnalyzer(AdaptiveSkipConfig(protection_window_frames=10))
    guard = EventProtectionGuard(analyzer)

    guard.check_and_protect(0, _make_motion_score(0), roi_proximity=True)
    guard.check_and_protect(1, _make_motion_score(1), roi_proximity=True)
    guard.check_and_protect(2, _make_motion_score(2), track_count_changed=True)

    stats = guard.stats
    by_reason = stats["triggers_by_reason"]
    assert by_reason.get("roi_proximity", 0) == 2
    assert by_reason.get("new_track_appeared", 0) == 1
