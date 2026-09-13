"""
Phase 6D.4 — Regression tests for StoryBuilder vocabulary alignment.

Tests:
  1. "running" as action event → COMPLETE story
  2. "walking_upstairs" as action event → COMPLETE story
  3. "walking_downstairs" as action event → COMPLETE story
  4. "person_crouching_sustained" as action event → NOT COMPLETE (not in _ACTION_EVENTS)
  5. entry + recognized action + exit → COMPLETE
  6. entry + unrecognized arbitrary event + exit → PARTIAL (not COMPLETE)
  7. cycling story behavior still correct (regression from Phase 6D)
  8. "person_running" (EventType) still recognized (no regression)
  9. "person_walking" (EventType) still recognized (no regression)
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.engines.temporal.story_preservation.story_builder import (
    StoryBuilder,
    StoryCompleteness,
    _ACTION_EVENTS,
    _ENTRY_EVENTS,
    _EXIT_EVENTS,
)
from app.engines.semantic.event_understanding.engine import Event
from app.engines.semantic.event_understanding.rules import EventType


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_event(event_type: str, track_id: int, start_ms: float = 0.0) -> Event:
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        track_id=track_id,
        class_name="person",
        rule_name="test",
        confidence=0.80,
        evidence={"test": True},
        start_frame=int(start_ms / 33),
        end_frame=int(start_ms / 33) + 5,
        start_ms=start_ms,
        end_ms=start_ms + 1000.0,
    )


def build_story(events: list[Event]) -> "StoryPreservationResult":
    """Run StoryBuilder on a minimal event list and return result."""
    from app.engines.temporal.story_preservation.config import StoryConfig
    cfg = StoryConfig()
    builder = StoryBuilder(config=cfg)
    return builder.build(events=events)



def complete_story_events(track_id: int, action_type: str) -> list[Event]:
    """Create entry + action + exit for a single track."""
    return [
        make_event(EventType.PERSON_ENTERED_SCENE, track_id, start_ms=0.0),
        make_event(action_type,                    track_id, start_ms=5000.0),
        make_event(EventType.PERSON_LEFT_SCENE,    track_id, start_ms=10000.0),
    ]


# ===========================================================================
# 1. "running" as action event → COMPLETE story
# ===========================================================================

class TestRunningActionEvent:

    def test_running_in_action_events_set(self):
        """'running' must be present in _ACTION_EVENTS after Phase 6D.4 fix."""
        assert "running" in _ACTION_EVENTS, (
            "Phase 6D.4: 'running' must be in _ACTION_EVENTS. "
            "ActivityClassifier emits this label; narrative_builder passes it as event_type."
        )

    def test_entry_running_exit_is_complete_story(self):
        """person_entered + running + person_left → COMPLETE story."""
        events = complete_story_events(track_id=101, action_type="running")
        result = build_story(events)
        complete_segs = [s for s in result.segments
                         if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete_segs) >= 1, (
            f"Track 101 with entry+running+exit should produce COMPLETE story. "
            f"Got segments: {[(s.track_id, s.completeness) for s in result.segments]}"
        )

    def test_running_action_is_counted_in_complete_segments(self):
        """result.complete_segments increases when 'running' is recognized."""
        events = complete_story_events(track_id=102, action_type="running")
        result = build_story(events)
        assert result.complete_segments >= 1, (
            f"complete_segments should be ≥1 for track with running action. "
            f"Got: {result.complete_segments}"
        )


# ===========================================================================
# 2. "walking_upstairs" as action event → COMPLETE story
# ===========================================================================

class TestWalkingUpstairsActionEvent:

    def test_walking_upstairs_in_action_events_set(self):
        """'walking_upstairs' must be present in _ACTION_EVENTS after Phase 6D.4."""
        assert "walking_upstairs" in _ACTION_EVENTS, (
            "Phase 6D.4: 'walking_upstairs' must be in _ACTION_EVENTS. "
            "ActivityClassifier._detect_stairs() emits this label."
        )

    def test_entry_walking_upstairs_exit_is_complete(self):
        """person_entered + walking_upstairs + person_left → COMPLETE story."""
        events = complete_story_events(track_id=201, action_type="walking_upstairs")
        result = build_story(events)
        complete_segs = [s for s in result.segments
                         if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete_segs) >= 1, (
            f"Track 201 with entry+walking_upstairs+exit should produce COMPLETE story. "
            f"Got segments: {[(s.track_id, s.completeness) for s in result.segments]}"
        )


# ===========================================================================
# 3. "walking_downstairs" as action event → COMPLETE story
# ===========================================================================

class TestWalkingDownstairsActionEvent:

    def test_walking_downstairs_in_action_events_set(self):
        """'walking_downstairs' must be present in _ACTION_EVENTS after Phase 6D.4."""
        assert "walking_downstairs" in _ACTION_EVENTS, (
            "Phase 6D.4: 'walking_downstairs' must be in _ACTION_EVENTS. "
            "ActivityClassifier._detect_stairs() emits this label."
        )

    def test_entry_walking_downstairs_exit_is_complete(self):
        """person_entered + walking_downstairs + person_left → COMPLETE story."""
        events = complete_story_events(track_id=301, action_type="walking_downstairs")
        result = build_story(events)
        complete_segs = [s for s in result.segments
                         if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete_segs) >= 1, (
            f"Track 301 with entry+walking_downstairs+exit should produce COMPLETE story. "
            f"Got segments: {[(s.track_id, s.completeness) for s in result.segments]}"
        )


# ===========================================================================
# 4. "person_crouching_sustained" NOT added → not automatically COMPLETE
# ===========================================================================

class TestCrouchingNotAddedYet:

    def test_crouching_sustained_not_in_action_events(self):
        """
        'person_crouching_sustained' must NOT be in _ACTION_EVENTS yet.
        Phase 6D.4 explicitly deferred this — TemporalPoseAnalyzer thresholds
        are not yet calibrated.
        """
        assert "person_crouching_sustained" not in _ACTION_EVENTS, (
            "Phase 6D.4: 'person_crouching_sustained' should NOT be in _ACTION_EVENTS. "
            "Its source (TemporalPoseAnalyzer) notes thresholds are uncalibrated."
        )

    def test_entry_crouching_exit_is_not_complete(self):
        """person_entered + person_crouching_sustained + person_left → PARTIAL, not COMPLETE."""
        events = complete_story_events(track_id=401, action_type="person_crouching_sustained")
        result = build_story(events)
        complete_segs = [s for s in result.segments
                         if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete_segs) == 0, (
            f"Crouching-only story should NOT be COMPLETE (not in _ACTION_EVENTS). "
            f"Got COMPLETE: {len(complete_segs)}"
        )


# ===========================================================================
# 5. entry + recognized action + exit → COMPLETE (general contract)
# ===========================================================================

class TestStoryCompletenessContract:

    @pytest.mark.parametrize("action_type", [
        "running",           # Phase 6D.4
        "walking_upstairs",  # Phase 6D.4
        "walking_downstairs", # Phase 6D.4
        "cycling",           # Phase 6D
        EventType.PERSON_WALKING,   # baseline
        EventType.PERSON_RUNNING,   # baseline
        EventType.PERSON_STANDING,  # baseline
        EventType.VEHICLE_APPROACHING,  # baseline
    ])
    def test_recognized_action_produces_complete_story(self, action_type: str):
        """Each recognized action type, with entry+exit, should produce COMPLETE."""
        events = complete_story_events(track_id=500, action_type=action_type)
        result = build_story(events)
        complete = [s for s in result.segments if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete) >= 1, (
            f"Action '{action_type}' with entry+exit should produce COMPLETE story. "
            f"Segments: {[(s.track_id, s.completeness) for s in result.segments]}"
        )


# ===========================================================================
# 6. entry + arbitrary unrecognized event + exit → NOT COMPLETE
# ===========================================================================

class TestUnrecognizedActionNotComplete:

    @pytest.mark.parametrize("unknown_type", [
        "person_crouching_sustained",   # explicitly deferred
        "person_reaching_up",            # gesture, not action
        "light_turned_on",               # scene-level, not person action
        "group_gathering",               # group, not individual
        "unknown_event_type_xyz",        # completely unknown
    ])
    def test_unrecognized_action_does_not_produce_complete(self, unknown_type: str):
        """Unknown/unrecognized action event should NOT make story COMPLETE."""
        events = complete_story_events(track_id=600, action_type=unknown_type)
        result = build_story(events)
        complete = [s for s in result.segments if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete) == 0, (
            f"Unrecognized action '{unknown_type}' should NOT produce COMPLETE story. "
            f"Got COMPLETE: {len(complete)}"
        )


# ===========================================================================
# 7. cycling story behavior regression (Phase 6D fix preserved)
# ===========================================================================

class TestCyclingStoryRegression:

    def test_cycling_still_in_action_events(self):
        """'cycling' must still be in _ACTION_EVENTS (Phase 6D fix preserved)."""
        assert "cycling" in _ACTION_EVENTS, (
            "Phase 6D regression: 'cycling' must remain in _ACTION_EVENTS."
        )

    def test_cycling_story_still_complete(self):
        """entry + cycling + exit → COMPLETE (regression from Phase 6D)."""
        events = complete_story_events(track_id=701, action_type="cycling")
        result = build_story(events)
        complete = [s for s in result.segments if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete) >= 1, (
            f"Phase 6D regression: cycling story should still be COMPLETE. "
            f"Got segments: {[(s.track_id, s.completeness) for s in result.segments]}"
        )


# ===========================================================================
# 8. EventType.PERSON_RUNNING ("person_running") still recognized
# ===========================================================================

class TestEventTypeConstantsPreserved:

    def test_person_running_still_recognized(self):
        """'person_running' (EventType.PERSON_RUNNING) still in _ACTION_EVENTS."""
        assert EventType.PERSON_RUNNING in _ACTION_EVENTS, (
            "EventType.PERSON_RUNNING must remain in _ACTION_EVENTS. "
            "Activity state machine emits this label."
        )

    def test_person_walking_still_recognized(self):
        """'person_walking' (EventType.PERSON_WALKING) still in _ACTION_EVENTS."""
        assert EventType.PERSON_WALKING in _ACTION_EVENTS, (
            "EventType.PERSON_WALKING must remain in _ACTION_EVENTS."
        )

    def test_person_standing_still_recognized(self):
        """'person_standing' (EventType.PERSON_STANDING) still in _ACTION_EVENTS."""
        assert EventType.PERSON_STANDING in _ACTION_EVENTS

    def test_entry_person_running_exit_still_complete(self):
        """entry + person_running + exit → COMPLETE (state machine path preserved)."""
        events = complete_story_events(track_id=801, action_type=EventType.PERSON_RUNNING)
        result = build_story(events)
        complete = [s for s in result.segments if s.completeness == StoryCompleteness.COMPLETE]
        assert len(complete) >= 1, (
            f"'person_running' (EventType) story should still be COMPLETE. "
            f"Got segments: {[(s.track_id, s.completeness) for s in result.segments]}"
        )


# ===========================================================================
# 9. Multiple tracks — independent story classification
# ===========================================================================

class TestMultiTrackStoryClassification:

    def test_mixed_recognized_and_unrecognized_actions(self):
        """Two tracks: one with recognized action (COMPLETE), one without (PARTIAL)."""
        track_complete_events = complete_story_events(track_id=901, action_type="running")
        track_partial_events = complete_story_events(track_id=902, action_type="person_crouching_sustained")

        all_events = track_complete_events + track_partial_events
        result = build_story(all_events)

        complete = [s for s in result.segments
                    if s.completeness == StoryCompleteness.COMPLETE]
        partial = [s for s in result.segments
                   if s.completeness != StoryCompleteness.COMPLETE]

        assert len(complete) >= 1, (
            f"Track 901 (running) should produce COMPLETE story."
        )
        # Track 902 with crouching should not be COMPLETE
        track_902_complete = [s for s in complete if 902 in s.track_ids]
        assert len(track_902_complete) == 0, (
            f"Track 902 (crouching) should NOT produce COMPLETE story."
        )
