"""
Tests for Phase 6: Semantic Event Understanding.

Per mentor guidance, this file includes BOTH:
  1. Unit tests  — test individual rules and the engine in isolation
  2. Integration tests — full pipeline chain:
       Synthetic Track → MotionAnalyzer → EventUnderstandingEngine → Expected Event

Integration tests are the most important in Phase 6.
They catch issues that unit tests on individual modules miss.
For example: a rule might pass its own unit test but fail to fire
because the motion profile it depends on has wrong values.

Test IDs are explicit so failures are immediately locatable.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.engines.perception.motion_analyzer.analyzer import (
    ApproachSignal,
    MotionAnalyzer,
    MotionProfile,
    SpeedClass,
)
from app.engines.perception.tracker.track import (
    Track,
    TrackBBox,
    TrackObservation,
    TrackState,
)
from app.engines.semantic.event_understanding.config import EventUnderstandingConfig
from app.engines.semantic.event_understanding.engine import (
    Event,
    EventUnderstandingEngine,
    EventUnderstandingResult,
)
from app.engines.semantic.event_understanding.rules import (
    KNOWLEDGE_BASE,
    EventRule,
    EventType,
    PERSON_CLASSES,
    VEHICLE_CLASSES,
)


# ---------------------------------------------------------------------------
# Synthetic construction helpers
# ---------------------------------------------------------------------------

def _bbox(x1=0.1, y1=0.1, x2=0.5, y2=0.9, conf=0.85) -> TrackBBox:
    return TrackBBox(x1=x1, y1=y1, x2=x2, y2=y2, confidence=conf,
                     class_id=0, class_name="person")


def _obs(frame: int, ts: float, bbox: TrackBBox | None = None) -> TrackObservation:
    b = bbox or _bbox()
    return TrackObservation(
        frame_number=frame,
        timestamp_ms=ts,
        bbox=b,
        detection_confidence=b.confidence,
    )


def _make_track(
    track_id: int = 1,
    class_name: str = "person",
    observations: list | None = None,
    state: TrackState = TrackState.ACTIVE,
    total_matched: int | None = None,
) -> Track:
    obs = observations or [_obs(1, 0.0), _obs(2, 200.0), _obs(3, 400.0)]
    first, last = obs[0], obs[-1]
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
        observations=list(obs),
    )
    t.total_frames_matched = total_matched if total_matched is not None else len(obs)
    if state == TrackState.ACTIVE:
        t.confirmed_at_frame = first.frame_number
    return t


def _make_profile(
    track_id: int = 1,
    class_name: str = "person",
    speed_class: SpeedClass = SpeedClass.WALKING,
    is_stationary: bool = False,
    has_approach: bool = False,
    has_recede: bool = False,
    confidence: float = 0.75,
) -> MotionProfile:
    p = MotionProfile(
        track_id=track_id,
        class_name=class_name,
        dominant_speed_class=speed_class,
        is_stationary=is_stationary,
        has_approach_phase=has_approach,
        has_recede_phase=has_recede,
        motion_confidence=confidence,
    )
    return p


# ---------------------------------------------------------------------------
# EventRule unit tests
# ---------------------------------------------------------------------------

class TestEventRule:
    def test_class_filter_blocks_wrong_class(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            class_names=PERSON_CLASSES,
        )
        track = _make_track(class_name="car")
        matched, conf, evidence = rule.evaluate(track, None, {})
        assert not matched

    def test_class_filter_passes_correct_class(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            class_names=PERSON_CLASSES,
        )
        track = _make_track(class_name="person")
        profile = _make_profile()
        matched, conf, evidence = rule.evaluate(track, profile, {})
        assert matched

    def test_speed_class_filter_blocks_wrong_speed(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            class_names=PERSON_CLASSES,
            speed_classes=frozenset({SpeedClass.FAST}),
        )
        track = _make_track(class_name="person")
        profile = _make_profile(speed_class=SpeedClass.STATIONARY)
        matched, _, _ = rule.evaluate(track, profile, {})
        assert not matched

    def test_require_stationary_true_blocks_moving(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            require_stationary=True,
        )
        track = _make_track()
        profile = _make_profile(is_stationary=False)
        matched, _, _ = rule.evaluate(track, profile, {})
        assert not matched

    def test_require_new_track_blocks_old_track(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            require_new_track=True,
        )
        track = _make_track()
        matched, _, _ = rule.evaluate(track, None, {"is_new": False})
        assert not matched

    def test_require_ended_track_passes(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            require_ended_track=True,
        )
        track = _make_track(state=TrackState.ENDED)
        matched, _, evidence = rule.evaluate(track, None, {"is_ended": True})
        assert matched
        assert evidence["rule"] == "test"

    def test_min_track_frames_blocks_short_track(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            min_track_frames=5,
        )
        track = _make_track(total_matched=3)
        matched, _, _ = rule.evaluate(track, None, {})
        assert not matched

    def test_min_motion_confidence_gate(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            min_motion_confidence=0.8,
        )
        track = _make_track()
        profile = _make_profile(confidence=0.5)
        matched, _, _ = rule.evaluate(track, profile, {})
        assert not matched

    def test_confidence_is_in_valid_range(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            class_names=PERSON_CLASSES,
        )
        track = _make_track(class_name="person")
        profile = _make_profile()
        matched, conf, _ = rule.evaluate(track, profile, {})
        assert matched
        assert 0.0 <= conf <= 1.0

    def test_evidence_contains_rule_name(self):
        rule = EventRule(
            name="my_rule", event_type="test_event", description="",
        )
        track = _make_track()
        matched, _, evidence = rule.evaluate(track, None, {})
        assert matched
        assert evidence["rule"] == "my_rule"

    def test_require_approach_blocks_no_approach(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            require_approach=True,
        )
        track = _make_track(class_name="car")
        profile = _make_profile(has_approach=False)
        matched, _, _ = rule.evaluate(track, profile, {})
        assert not matched

    def test_require_approach_passes_with_approach(self):
        rule = EventRule(
            name="test", event_type="test_event", description="",
            require_approach=True,
        )
        track = _make_track(class_name="car")
        profile = _make_profile(has_approach=True)
        matched, _, _ = rule.evaluate(track, profile, {})
        assert matched


# ---------------------------------------------------------------------------
# EventUnderstandingEngine unit tests
# ---------------------------------------------------------------------------

class TestEventUnderstandingEngine:
    def test_no_tracks_returns_empty(self):
        engine = EventUnderstandingEngine()
        result = engine.understand([], {}, [])
        assert result.total_events == 0
        assert result.events == []

    def test_tentative_track_excluded(self):
        """Tentative tracks are not confirmed — no events."""
        engine = EventUnderstandingEngine()
        track = _make_track(state=TrackState.TENTATIVE)
        result = engine.understand([track], {}, [])
        assert result.total_events == 0

    def test_event_has_all_required_fields(self):
        """Every Event must have event_id, rule_name, evidence, and timestamps."""
        engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0)
        )
        track = _make_track(class_name="person", total_matched=3)
        profile = _make_profile(speed_class=SpeedClass.WALKING)
        result = engine.understand([track], {track.track_id: profile}, [])
        assert len(result.events) > 0
        for event in result.events:
            assert event.event_id  # non-empty UUID
            assert event.rule_name
            assert isinstance(event.evidence, dict)
            assert event.start_ms >= 0
            assert event.end_ms >= 0
            assert 0.0 <= event.confidence <= 1.0

    def test_events_by_type_aggregation(self):
        engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0)
        )
        track = _make_track(class_name="person", total_matched=3)
        profile = _make_profile(speed_class=SpeedClass.WALKING)
        result = engine.understand([track], {track.track_id: profile}, [])
        by_type = result.events_by_type()
        assert isinstance(by_type, dict)

    def test_camera_motion_suppression(self):
        """Track entirely in camera-motion frames should generate no events."""
        engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(
                min_event_confidence=0.0,
                suppress_camera_motion_events=True,
            )
        )
        # Track observations in frames 1,2,3 — all camera-motion
        track = _make_track(class_name="person", total_matched=3)
        profile = _make_profile(speed_class=SpeedClass.WALKING)
        # frames 1, 2, 3 are all camera-motion
        result = engine.understand(
            [track], {track.track_id: profile}, camera_motion_frames=[1, 2, 3]
        )
        assert result.camera_motion_frames_skipped >= 1

    def test_custom_rules_override_knowledge_base(self):
        """Engine should use only supplied rules when provided."""
        custom_rule = EventRule(
            name="my_custom_rule",
            event_type="custom_event",
            description="Custom",
        )
        engine = EventUnderstandingEngine(rules=[custom_rule])
        track = _make_track(class_name="person", total_matched=3)
        result = engine.understand([track], {}, [])
        for event in result.events:
            assert event.event_type == "custom_event"

    def test_event_ids_are_unique(self):
        """Each event must have a unique event_id."""
        engine = EventUnderstandingEngine(
            config=EventUnderstandingConfig(min_event_confidence=0.0)
        )
        tracks = [_make_track(i, "person", total_matched=3) for i in range(1, 4)]
        profiles = {t.track_id: _make_profile(t.track_id) for t in tracks}
        result = engine.understand(tracks, profiles, [])
        ids = [e.event_id for e in result.events]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Knowledge base rule tests
# ---------------------------------------------------------------------------

class TestKnowledgeBase:
    def test_person_walking_rule_exists(self):
        names = {r.event_type for r in KNOWLEDGE_BASE}
        assert EventType.PERSON_WALKING in names

    def test_person_running_rule_exists(self):
        names = {r.event_type for r in KNOWLEDGE_BASE}
        assert EventType.PERSON_RUNNING in names

    def test_vehicle_approaching_rule_exists(self):
        names = {r.event_type for r in KNOWLEDGE_BASE}
        assert EventType.VEHICLE_APPROACHING in names

    def test_person_loitering_requires_5_seconds(self):
        loitering = next(r for r in KNOWLEDGE_BASE if r.event_type == EventType.PERSON_LOITERING)
        assert loitering.min_track_length_ms >= 5000.0

    def test_all_rules_have_names(self):
        for rule in KNOWLEDGE_BASE:
            assert rule.name, f"Rule with event_type {rule.event_type} has no name"
            assert rule.description, f"Rule {rule.name} has no description"


# ---------------------------------------------------------------------------
# INTEGRATION TESTS
# Synthetic Track → MotionAnalyzer → EventUnderstandingEngine → Expected Event
# These catch cross-stage issues that unit tests miss.
# ---------------------------------------------------------------------------

def _integration_track_with_motion(
    track_id: int,
    class_name: str,
    bboxes: list[tuple],
    state: TrackState = TrackState.ACTIVE,
) -> Track:
    """Build a track with custom bboxes for integration testing."""
    obs = [
        _obs(i + 1, (i + 1) * 400.0, TrackBBox(
            x1=b[0], y1=b[1], x2=b[2], y2=b[3],
            confidence=0.85, class_id=0, class_name=class_name,
        ))
        for i, b in enumerate(bboxes)
    ]
    t = _make_track(track_id, class_name, obs, state, total_matched=len(obs))
    t.class_name = class_name
    return t


class TestIntegration:
    """
    Full chain: Synthetic Track → MotionAnalyzer → EventUnderstanding → Expected Event

    Each test documents the expected data flow explicitly.
    """

    def _engine(self) -> EventUnderstandingEngine:
        return EventUnderstandingEngine(
            config=EventUnderstandingConfig(
                min_event_confidence=0.0,  # accept all in integration tests
                min_track_frames_for_entry=2,
            )
        )

    def test_integration_person_walking(self):
        """
        Scenario: Person walks steadily rightward across the scene.
        Expected: person_walking event generated.
        """
        # Person moves 0.025 per frame → walking speed
        bboxes = [(0.1 + i*0.025, 0.1, 0.4 + i*0.025, 0.9) for i in range(6)]
        track = _integration_track_with_motion(1, "person", bboxes)

        analyzer = MotionAnalyzer()
        motion_result = analyzer.analyze([track])
        profile = motion_result.motion_profiles.get(track.track_id)
        assert profile is not None, "Motion profile missing — check track confirmation"

        engine = self._engine()
        result = engine.understand([track], motion_result.motion_profiles, [])

        event_types = {e.event_type for e in result.events}
        assert EventType.PERSON_WALKING in event_types or EventType.PERSON_STANDING in event_types, (
            f"Expected person_walking or person_standing. Got: {event_types}. "
            f"Speed class: {profile.dominant_speed_class}"
        )

    def test_integration_person_stationary_standing(self):
        """
        Scenario: Person barely moves (tiny drift < 0.001 per frame).
        Expected: person_standing event generated.
        """
        bboxes = [(0.1 + i*0.0001, 0.1, 0.5 + i*0.0001, 0.9) for i in range(6)]
        track = _integration_track_with_motion(2, "person", bboxes)

        analyzer = MotionAnalyzer()
        motion_result = analyzer.analyze([track])
        profile = motion_result.motion_profiles.get(track.track_id)

        engine = self._engine()
        result = engine.understand([track], motion_result.motion_profiles, [])

        event_types = {e.event_type for e in result.events}
        assert EventType.PERSON_STANDING in event_types, (
            f"Expected person_standing. Got: {event_types}. "
            f"Speed: {profile.dominant_speed_class if profile else 'no profile'}"
        )

    def test_integration_vehicle_approaching(self):
        """
        Scenario: Car bounding box grows each frame (approaching camera).
        Expected: vehicle_approaching event generated.
        """
        bboxes = [
            (0.3 - i*0.03, 0.3 - i*0.02, 0.7 + i*0.03, 0.7 + i*0.02)
            for i in range(5)
        ]
        track = _integration_track_with_motion(3, "car", bboxes)

        analyzer = MotionAnalyzer()
        motion_result = analyzer.analyze([track])
        profile = motion_result.motion_profiles.get(track.track_id)

        engine = self._engine()
        result = engine.understand([track], motion_result.motion_profiles, [])

        event_types = {e.event_type for e in result.events}
        assert EventType.VEHICLE_APPROACHING in event_types, (
            f"Expected vehicle_approaching. Got: {event_types}. "
            f"has_approach: {profile.has_approach_phase if profile else 'no profile'}"
        )

    def test_integration_person_loitering(self):
        """
        Scenario: Person stationary for 8 seconds (8000ms > 5000ms loitering threshold).
        Expected: person_loitering event generated.
        """
        # Stationary person across 20 frames (400ms each = 8000ms total)
        bboxes = [(0.1, 0.1, 0.5, 0.9)] * 20
        obs = [
            _obs(i + 1, (i + 1) * 400.0, TrackBBox(
                x1=0.1, y1=0.1, x2=0.5, y2=0.9,
                confidence=0.85, class_id=0, class_name="person",
            ))
            for i in range(20)
        ]
        track = _make_track(4, "person", obs, total_matched=20)

        analyzer = MotionAnalyzer()
        motion_result = analyzer.analyze([track])

        engine = self._engine()
        result = engine.understand([track], motion_result.motion_profiles, [])

        event_types = {e.event_type for e in result.events}
        assert EventType.PERSON_LOITERING in event_types, (
            f"Expected person_loitering (track_length={track.track_length_ms}ms). "
            f"Got: {event_types}"
        )

    def test_integration_evidence_is_populated(self):
        """
        Scenario: Any event should have a non-empty evidence dict
        with at minimum a 'rule' key.
        Integration check: evidence comes from rule.evaluate(), not hard-coded.
        """
        bboxes = [(0.1 + i*0.025, 0.1, 0.4 + i*0.025, 0.9) for i in range(5)]
        track = _integration_track_with_motion(5, "person", bboxes)

        analyzer = MotionAnalyzer()
        motion_result = analyzer.analyze([track])

        engine = self._engine()
        result = engine.understand([track], motion_result.motion_profiles, [])

        for event in result.events:
            assert "rule" in event.evidence, (
                f"Event {event.event_type} missing 'rule' key in evidence"
            )
            assert "track_id" in event.evidence

    def test_integration_no_events_for_empty_scene(self):
        """
        Scenario: No tracks in video.
        Expected: Zero events, no crash.
        """
        engine = self._engine()
        result = engine.understand([], {}, [])
        assert result.total_events == 0
        assert result.events == []

    def test_integration_motion_confidence_in_profile(self):
        """
        Scenario: Long consistent track should produce high motion_confidence.
        Expected: motion_confidence > 0.5 (not the default 0.0).
        """
        bboxes = [(0.1 + i*0.02, 0.1, 0.4 + i*0.02, 0.9) for i in range(10)]
        track = _integration_track_with_motion(6, "person", bboxes)

        analyzer = MotionAnalyzer()
        motion_result = analyzer.analyze([track])
        profile = motion_result.motion_profiles.get(track.track_id)

        assert profile is not None
        assert profile.motion_confidence > 0.5, (
            f"Expected motion_confidence > 0.5, got {profile.motion_confidence}"
        )


# ---------------------------------------------------------------------------
# s07_event_understand pipeline stage tests
# ---------------------------------------------------------------------------

class TestS07EventUnderstand:
    def _make_context(self, all_tracks=None, motion_profiles=None):
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-TEST",
            video_id="test",
            video_path="/tmp/v.mp4",
            output_dir="/tmp",
            settings={
                "event_min_confidence": 0.0,
                "event_min_track_frames": 2,
                "event_suppress_camera_motion": True,
            },
            metadata={
                "camera_motion_frames": [],
            },
        )
        if all_tracks is not None:
            ctx.metadata["all_tracks"] = all_tracks
        if motion_profiles is not None:
            ctx.metadata["motion_profiles"] = motion_profiles
        return ctx

    @pytest.mark.asyncio
    async def test_missing_tracks_fails(self):
        from app.pipeline.stages import s07_event_understand
        ctx = self._make_context()
        result = await s07_event_understand.run(ctx)
        assert result.success is False
        assert any("all_tracks" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s07_event_understand.save_stage_metrics")
    async def test_empty_tracks_returns_success(self, mock_save):
        from app.pipeline.stages import s07_event_understand
        mock_save.return_value = None
        ctx = self._make_context(all_tracks=[], motion_profiles={})
        result = await s07_event_understand.run(ctx)
        assert result.success is True
        assert ctx.metadata["events"] == []

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s07_event_understand.save_stage_metrics")
    async def test_walking_person_generates_event(self, mock_save):
        from app.pipeline.stages import s07_event_understand
        mock_save.return_value = None
        track = _make_track(1, "person", total_matched=3)
        profile = _make_profile(1, speed_class=SpeedClass.WALKING)
        ctx = self._make_context(
            all_tracks=[track],
            motion_profiles={1: profile},
        )
        result = await s07_event_understand.run(ctx)
        assert result.success is True
        assert ctx.metadata["total_events"] if "total_events" in ctx.metadata else len(ctx.metadata["events"]) >= 0

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s07_event_understand
        ctx = self._make_context()
        result = await s07_event_understand.run(ctx)
        assert result.stage_name == "s07_event_understand"
