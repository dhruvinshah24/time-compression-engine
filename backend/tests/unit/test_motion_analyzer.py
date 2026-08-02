"""
Unit tests for Phase 5: Motion Analysis.

Coverage:
  1. SpeedClass classification — all four bands
  2. Direction classification — all 8 compass points + stationary
  3. ApproachSignal — approach, recede, stable
  4. VelocityObservation computation from track pairs
  5. MotionProfile — stationary/moving, approach/recede flags
  6. Camera motion detection — coherent vs incoherent velocity
  7. MotionAnalyzer end-to-end with synthetic tracks
  8. MotionAnalyzer with single-observation tracks (skipped — no pairs)
  9. s06_motion_analyze pipeline stage (mocked)

Synthetic track construction:
  Build Track objects directly with known observation histories,
  so test outcomes are fully deterministic.
"""

from __future__ import annotations

import math
from unittest.mock import patch

import numpy as np
import pytest

from app.engines.perception.motion_analyzer.analyzer import (
    ApproachSignal,
    Direction,
    MotionAnalyzer,
    MotionAnalysisResult,
    MotionProfile,
    SpeedClass,
    VelocityObservation,
)
from app.engines.perception.motion_analyzer.config import MotionAnalyzerConfig
from app.engines.perception.tracker.track import (
    Track,
    TrackBBox,
    TrackObservation,
    TrackState,
)


# ---------------------------------------------------------------------------
# Helpers: build synthetic tracks
# ---------------------------------------------------------------------------

def _bbox(x1: float, y1: float, x2: float, y2: float, conf: float = 0.85) -> TrackBBox:
    return TrackBBox(x1=x1, y1=y1, x2=x2, y2=y2,
                     confidence=conf, class_id=0, class_name="person")


def _obs(frame: int, ts: float, bbox: TrackBBox) -> TrackObservation:
    return TrackObservation(
        frame_number=frame,
        timestamp_ms=ts,
        bbox=bbox,
        detection_confidence=bbox.confidence,
    )


def _track(
    track_id: int,
    observations: list[TrackObservation],
    state: TrackState = TrackState.ACTIVE,
    class_name: str = "person",
) -> Track:
    first = observations[0]
    last = observations[-1]
    t = Track(
        track_id=track_id,
        class_name=class_name,
        class_id=0,
        state=state,
        created_frame=first.frame_number,
        created_timestamp_ms=first.timestamp_ms,
        last_seen_frame=last.frame_number,
        last_seen_timestamp_ms=last.timestamp_ms,
        current_bbox=last.bbox,
        observations=list(observations),
    )
    t.total_frames_matched = len(observations)
    if state == TrackState.ACTIVE:
        t.confirmed_at_frame = first.frame_number
    return t


def _stationary_track(track_id: int = 1, n_frames: int = 5) -> Track:
    """Track that barely moves — should be STATIONARY."""
    obs = [
        _obs(i, i * 200.0, _bbox(0.1 + i * 0.0001, 0.1, 0.5 + i * 0.0001, 0.9))
        for i in range(1, n_frames + 1)
    ]
    return _track(track_id, obs)


def _walking_track(track_id: int = 2, n_frames: int = 5) -> Track:
    """Track that moves steadily rightward — should be WALKING."""
    obs = [
        _obs(i, i * 200.0, _bbox(0.1 + i * 0.025, 0.1, 0.4 + i * 0.025, 0.9))
        for i in range(1, n_frames + 1)
    ]
    return _track(track_id, obs)


def _approaching_track(track_id: int = 3, n_frames: int = 5) -> Track:
    """Track whose bbox area grows each frame — approaching."""
    obs = [
        _obs(i, i * 200.0, _bbox(
            0.3 - i * 0.03, 0.3 - i * 0.03,
            0.7 + i * 0.03, 0.7 + i * 0.03
        ))
        for i in range(1, n_frames + 1)
    ]
    return _track(track_id, obs)


# ---------------------------------------------------------------------------
# SpeedClass classification tests
# ---------------------------------------------------------------------------

class TestSpeedClassification:
    def _analyzer(self) -> MotionAnalyzer:
        return MotionAnalyzer()

    def test_stationary_speed(self):
        analyzer = self._analyzer()
        assert analyzer._classify_speed(0.005) == SpeedClass.STATIONARY

    def test_slow_speed(self):
        analyzer = self._analyzer()
        assert analyzer._classify_speed(0.03) == SpeedClass.SLOW

    def test_walking_speed(self):
        analyzer = self._analyzer()
        assert analyzer._classify_speed(0.10) == SpeedClass.WALKING

    def test_fast_speed(self):
        analyzer = self._analyzer()
        assert analyzer._classify_speed(0.25) == SpeedClass.FAST

    def test_boundary_stationary_max(self):
        analyzer = self._analyzer()
        # Exactly at boundary → slow (not stationary)
        assert analyzer._classify_speed(0.01) == SpeedClass.SLOW


# ---------------------------------------------------------------------------
# Direction classification tests
# ---------------------------------------------------------------------------

class TestDirectionClassification:
    def _analyzer(self) -> MotionAnalyzer:
        return MotionAnalyzer()

    def test_east(self):
        analyzer = self._analyzer()
        assert analyzer._classify_direction(0.0) == Direction.E

    def test_north(self):
        analyzer = self._analyzer()
        assert analyzer._classify_direction(90.0) == Direction.N

    def test_west(self):
        analyzer = self._analyzer()
        assert analyzer._classify_direction(180.0) == Direction.W

    def test_south(self):
        analyzer = self._analyzer()
        assert analyzer._classify_direction(270.0) == Direction.S

    def test_northeast(self):
        analyzer = self._analyzer()
        assert analyzer._classify_direction(45.0) == Direction.NE

    def test_wraps_at_360(self):
        analyzer = self._analyzer()
        # 360 and 0 should give same result
        assert analyzer._classify_direction(360.0) == analyzer._classify_direction(0.0)


# ---------------------------------------------------------------------------
# ApproachSignal tests
# ---------------------------------------------------------------------------

class TestApproachSignal:
    def _analyzer(self) -> MotionAnalyzer:
        return MotionAnalyzer()

    def test_growing_box_is_approaching(self):
        analyzer = self._analyzer()
        result = analyzer._classify_approach(prev_area=0.10, curr_area=0.12)
        assert result == ApproachSignal.APPROACHING

    def test_shrinking_box_is_receding(self):
        analyzer = self._analyzer()
        result = analyzer._classify_approach(prev_area=0.10, curr_area=0.08)
        assert result == ApproachSignal.RECEDING

    def test_stable_area_is_stable(self):
        analyzer = self._analyzer()
        result = analyzer._classify_approach(prev_area=0.10, curr_area=0.103)
        assert result == ApproachSignal.STABLE

    def test_zero_prev_area_returns_stable(self):
        analyzer = self._analyzer()
        result = analyzer._classify_approach(prev_area=0.0, curr_area=0.1)
        assert result == ApproachSignal.STABLE


# ---------------------------------------------------------------------------
# Camera motion detection tests
# ---------------------------------------------------------------------------

class TestCameraMotionDetection:
    def test_coherent_velocities_detected(self):
        """All tracks moving right → camera motion."""
        analyzer = MotionAnalyzer(
            MotionAnalyzerConfig(min_tracks_for_camera_motion=2,
                                 camera_motion_coherence_threshold=0.8)
        )
        # All moving right
        velocities = [(0.01, 0.0), (0.012, 0.001), (0.011, -0.001)]
        coherence = analyzer._velocity_coherence(velocities)
        assert coherence > 0.9

    def test_random_velocities_low_coherence(self):
        """Random directions → low coherence → not camera motion."""
        analyzer = MotionAnalyzer()
        np.random.seed(42)
        velocities = [(np.random.randn(), np.random.randn()) for _ in range(10)]
        coherence = analyzer._velocity_coherence(velocities)
        assert coherence < 0.5

    def test_too_few_tracks_skips_detection(self):
        """Fewer tracks than min_tracks_for_camera_motion → no camera frames."""
        analyzer = MotionAnalyzer(
            MotionAnalyzerConfig(min_tracks_for_camera_motion=5)
        )
        track = _walking_track()
        result = analyzer.analyze([track])
        assert result.camera_motion_frames == []


# ---------------------------------------------------------------------------
# MotionAnalyzer end-to-end tests
# ---------------------------------------------------------------------------

class TestMotionAnalyzer:
    def test_stationary_track_classified_correctly(self):
        analyzer = MotionAnalyzer()
        track = _stationary_track()
        result = analyzer.analyze([track])
        profile = result.motion_profiles[track.track_id]
        assert profile.dominant_speed_class == SpeedClass.STATIONARY
        assert profile.is_stationary is True

    def test_walking_track_classified_correctly(self):
        analyzer = MotionAnalyzer()
        track = _walking_track()
        result = analyzer.analyze([track])
        profile = result.motion_profiles[track.track_id]
        assert profile.dominant_speed_class in (SpeedClass.WALKING, SpeedClass.SLOW)
        assert profile.is_stationary is False

    def test_approaching_track_has_approach_phase(self):
        analyzer = MotionAnalyzer()
        track = _approaching_track()
        result = analyzer.analyze([track])
        profile = result.motion_profiles[track.track_id]
        assert profile.has_approach_phase is True

    def test_empty_track_list_returns_empty_result(self):
        analyzer = MotionAnalyzer()
        result = analyzer.analyze([])
        assert result.motion_profiles == {}
        assert result.stationary_track_count == 0

    def test_single_observation_track_skipped(self):
        """Track with only 1 observation has no velocity pair — skip."""
        obs = [_obs(1, 0.0, _bbox(0.1, 0.1, 0.5, 0.9))]
        track = _track(1, obs)
        analyzer = MotionAnalyzer()
        result = analyzer.analyze([track])
        # Single obs track not in profiles (needs >= 2 obs)
        assert 1 not in result.motion_profiles

    def test_tentative_track_excluded(self):
        """Tentative tracks are not confirmed — should be excluded."""
        obs = [
            _obs(1, 0.0, _bbox(0.1, 0.1, 0.5, 0.9)),
            _obs(2, 200.0, _bbox(0.12, 0.1, 0.52, 0.9)),
        ]
        track = _track(1, obs, state=TrackState.TENTATIVE)
        analyzer = MotionAnalyzer()
        result = analyzer.analyze([track])
        assert 1 not in result.motion_profiles

    def test_motion_profile_has_all_expected_keys(self):
        analyzer = MotionAnalyzer()
        track = _walking_track()
        result = analyzer.analyze([track])
        d = result.motion_profiles[track.track_id].to_dict()
        for key in ["track_id", "class_name", "dominant_speed_class",
                    "dominant_direction", "avg_speed_per_second",
                    "is_stationary", "has_approach_phase", "has_recede_phase"]:
            assert key in d

    def test_metrics_dict_keys_present(self):
        analyzer = MotionAnalyzer()
        result = analyzer.analyze([_walking_track(), _stationary_track(2)])
        d = result.to_metrics_dict()
        for key in ["tracks_analyzed", "stationary_tracks", "moving_tracks",
                    "camera_motion_frames", "speed_class_distribution"]:
            assert key in d

    def test_stationary_moving_counts(self):
        analyzer = MotionAnalyzer()
        result = analyzer.analyze([
            _stationary_track(1),
            _walking_track(2),
            _walking_track(3),
        ])
        assert result.stationary_track_count == 1
        assert result.moving_track_count == 2


# ---------------------------------------------------------------------------
# s06_motion_analyze pipeline stage tests
# ---------------------------------------------------------------------------

class TestS06MotionAnalyze:
    def _make_context(self, all_tracks=None):
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-TEST",
            video_id="test",
            video_path="/tmp/v.mp4",
            output_dir="/tmp",
            settings={
                "motion_speed_stationary_max": 0.01,
                "motion_speed_slow_max": 0.05,
                "motion_speed_walking_max": 0.15,
                "motion_area_change_threshold": 0.05,
                "motion_camera_coherence_threshold": 0.85,
            },
            metadata={"fps": 25.0},
        )
        if all_tracks is not None:
            ctx.metadata["all_tracks"] = all_tracks
        return ctx

    @pytest.mark.asyncio
    async def test_missing_all_tracks_fails(self):
        from app.pipeline.stages import s06_motion_analyze
        ctx = self._make_context()
        result = await s06_motion_analyze.run(ctx)
        assert result.success is False
        assert any("all_tracks" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s06_motion_analyze.save_stage_metrics")
    async def test_empty_tracks_returns_success_with_warning(self, mock_save):
        from app.pipeline.stages import s06_motion_analyze
        mock_save.return_value = None
        ctx = self._make_context(all_tracks=[])
        result = await s06_motion_analyze.run(ctx)
        assert result.success is True
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s06_motion_analyze.save_stage_metrics")
    async def test_walking_track_stored_in_context(self, mock_save):
        from app.pipeline.stages import s06_motion_analyze
        mock_save.return_value = None
        track = _walking_track(track_id=7)
        ctx = self._make_context(all_tracks=[track])
        result = await s06_motion_analyze.run(ctx)
        assert result.success is True
        assert 7 in ctx.metadata["motion_profiles"]
        assert ctx.metadata["motion_profiles"][7].is_stationary is False

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s06_motion_analyze
        ctx = self._make_context()
        result = await s06_motion_analyze.run(ctx)
        assert result.stage_name == "s06_motion_analyze"
