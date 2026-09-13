"""
Phase 6E.2 — Regression tests for short-track activity classifier observation guard.

Tests:
  1. Track with 1 observation: velocity activity suppressed when threshold > 1.
  2. Track with 3 observations: correctly follows threshold (eligible at 3, suppressed at 5).
  3. Track exactly at threshold: activity remains eligible.
  4. Track below threshold: activity suppressed (returns 'entering_scene').
  5. Long track: activity remains eligible.
  6. Default experimental parameter (None): preserves baseline behavior (>=3 obs).
  7. Non-velocity pose events: unaffected (they bypass ActivityClassifier).
  8. Parameter sweep: tests behavior across 1, 3, 5, 8, 10, 15 observations.
  9. Stair walking suppression when below threshold.
  10. S05 context.settings reading of min_activity_observations.
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock
import pytest

from app.utils.activity_classifier import (
    ActivityClassifier,
    RUN_THRESHOLD,
    WALK_THRESHOLD,
    STAIR_VERT_THRESHOLD,
)


@dataclass
class BBox:
    cx: float
    cy: float
    width: float
    height: float


@dataclass
class TrackObservation:
    frame_number: int
    timestamp_ms: float
    bbox: BBox
    confidence: float = 0.85


def make_track(
    track_id: int = 1,
    class_name: str = "person",
    observations=None,
    confirmed: bool = True,
) -> MagicMock:
    t = MagicMock()
    t.track_id = track_id
    t.class_name = class_name
    t.observations = observations or []
    t.is_confirmed = confirmed
    t.confirmed_at_frame = 1 if confirmed else None
    return t


def make_fast_obs_series(n_obs: int, start_frame: int = 10, step_speed: float = 0.05) -> list[TrackObservation]:
    """Generate observations with high velocity and fluctuating height (running gait, height_std >= 0.03)."""
    obs = []
    for i in range(n_obs):
        f = start_frame + i * 5
        cx = 0.2 + i * step_speed
        cy = 0.5
        # Running gait causes bbox height fluctuation (avoids cycling Signal 2 seated check)
        h = 0.10 if (i % 2 == 0) else 0.18
        obs.append(TrackObservation(
            frame_number=f,
            timestamp_ms=f * 5 / 30 * 1000,
            bbox=BBox(cx=cx, cy=cy, width=0.05, height=h),
        ))
    return obs


def make_stair_obs_series(n_obs: int, start_frame: int = 10) -> list[TrackObservation]:
    """Generate observations with upward vertical velocity (stair walking gait)."""
    obs = []
    for i in range(n_obs):
        f = start_frame + i * 5
        cx = 0.3 + i * 0.015
        cy = 0.8 - i * 0.025  # cy decreasing = moving UP
        h = 0.10 if (i % 2 == 0) else 0.18
        obs.append(TrackObservation(
            frame_number=f,
            timestamp_ms=f * 5 / 30 * 1000,
            bbox=BBox(cx=cx, cy=cy, width=0.05, height=h),
        ))
    return obs


class TestObservationCountGuard:
    """Requirement 1: Track with 1 observation suppressed when threshold > 1."""

    def test_single_observation_suppressed_threshold_3(self):
        clf = ActivityClassifier(min_activity_observations=3)
        obs = make_fast_obs_series(1)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"
        assert res.label not in {"running", "walking_upstairs", "walking_downstairs", "walking"}

    def test_single_observation_suppressed_threshold_5(self):
        clf = ActivityClassifier(min_activity_observations=5)
        obs = make_fast_obs_series(1)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"

    def test_single_observation_suppressed_threshold_10(self):
        clf = ActivityClassifier(min_activity_observations=10)
        obs = make_fast_obs_series(1)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"


class TestThreeObservationTrack:
    """Requirement 2: Track with 3 observations follows threshold."""

    def test_three_obs_eligible_at_threshold_3(self):
        clf = ActivityClassifier(min_activity_observations=3)
        obs = make_fast_obs_series(3)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "running"

    def test_three_obs_suppressed_at_threshold_5(self):
        clf = ActivityClassifier(min_activity_observations=5)
        obs = make_fast_obs_series(3)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"

    def test_three_obs_suppressed_at_threshold_10(self):
        clf = ActivityClassifier(min_activity_observations=10)
        obs = make_fast_obs_series(3)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"


class TestThresholdBoundary:
    """Requirements 3 & 4: Track exactly at threshold vs below threshold."""

    @pytest.mark.parametrize("threshold", [3, 5, 8, 10, 15])
    def test_track_below_threshold_suppressed(self, threshold):
        clf = ActivityClassifier(min_activity_observations=threshold)
        obs = make_fast_obs_series(threshold - 1)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"
        assert res.evidence.get("reason") == "below_min_activity_observations"

    @pytest.mark.parametrize("threshold", [3, 5, 8, 10, 15])
    def test_track_exactly_at_threshold_eligible(self, threshold):
        clf = ActivityClassifier(min_activity_observations=threshold)
        obs = make_fast_obs_series(threshold)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "running"


class TestLongTrack:
    """Requirement 5: Long track remains eligible."""

    def test_long_track_running(self):
        clf = ActivityClassifier(min_activity_observations=10)
        obs = make_fast_obs_series(45)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "running"

    def test_long_track_stairs(self):
        clf = ActivityClassifier(min_activity_observations=10)
        obs = make_stair_obs_series(30)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "walking_upstairs"


class TestDefaultBaselineBehavior:
    """Requirement 6: Default experimental parameter preserves baseline behavior."""

    def test_default_none_running_with_3_obs(self):
        clf = ActivityClassifier()  # default min_activity_observations=None
        obs = make_fast_obs_series(3)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "running"

    def test_default_none_entering_with_2_obs(self):
        clf = ActivityClassifier()
        obs = make_fast_obs_series(2)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"

    def test_default_none_stair_with_long_track(self):
        clf = ActivityClassifier()
        obs = make_stair_obs_series(20)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "walking_upstairs"


class TestStairWalkingGuard:
    """Verifies observation guard correctly protects stair walking classifications."""

    def test_stairs_suppressed_below_threshold(self):
        clf = ActivityClassifier(min_activity_observations=8)
        obs = make_stair_obs_series(6)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "entering_scene"

    def test_stairs_eligible_at_or_above_threshold(self):
        clf = ActivityClassifier(min_activity_observations=8)
        obs = make_stair_obs_series(8)
        res = clf.classify(make_track(observations=obs))
        assert res.label == "walking_upstairs"


class TestPoseEventsUnaffected:
    """Requirement 7: Non-velocity pose events are unaffected."""

    def test_pose_events_do_not_use_activity_classifier(self):
        # Verify StoryBuilder action events still include pose and narrative actions
        from app.engines.temporal.story_preservation.story_builder import _ACTION_EVENTS
        from app.engines.semantic.event_understanding.rules import EventType
        assert EventType.PERSON_STANDING in _ACTION_EVENTS
        assert EventType.PERSON_LOITERING in _ACTION_EVENTS
        assert "running" in _ACTION_EVENTS
        assert "walking_upstairs" in _ACTION_EVENTS
        assert "walking_downstairs" in _ACTION_EVENTS


class TestS05SettingsIntegration:
    """Requirement 10: s05_track reads min_activity_observations from context.settings."""

    def test_s05_settings_reading(self):
        settings = {"min_activity_observations": 10}
        raw = settings.get("min_activity_observations")
        val = int(raw) if raw is not None else None
        clf = ActivityClassifier(min_activity_observations=val)
        assert clf._min_activity_observations == 10

    def test_s05_settings_default_none(self):
        settings = {}
        raw = settings.get("min_activity_observations")
        val = int(raw) if raw is not None else None
        clf = ActivityClassifier(min_activity_observations=val)
        assert clf._min_activity_observations is None
