"""
Phase 6D Regression Tests — StoryBuilder cycling vocabulary fix.

Tests prove:
  1. "cycling" is recognized as an action event in _ACTION_EVENTS.
  2. entry+cycling+exit produces StoryCompleteness.COMPLETE.
  3. Existing non-cycling COMPLETE behavior is unchanged.
  4. Existing PARTIAL behavior (missing events) is unchanged.
  5. Events that are NOT recognized as actions still produce PARTIAL.
  6. All tests use the actual production vocabulary (EventType constants
     and the literal "cycling" string emitted by narrative_builder).

No StoryBuilder thresholds or requirements are weakened to pass these tests.
"""
from __future__ import annotations

import uuid

import pytest

from app.engines.temporal.story_preservation.story_builder import (
    StoryBuilder, StoryCompleteness, _ACTION_EVENTS, _ENTRY_EVENTS, _EXIT_EVENTS,
)
from app.engines.semantic.event_understanding.engine import Event
from app.engines.semantic.event_understanding.rules import EventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evt(event_type: str, track_id: int = 1, start_ms: float = 0.0,
         end_ms: float = 1000.0, confidence: float = 0.80) -> Event:
    """Build a minimal Event for test use."""
    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        track_id=track_id,
        class_name="person",
        rule_name="test",
        confidence=confidence,
        evidence={},
        start_frame=int(start_ms // 33),
        end_frame=int(end_ms // 33),
        start_ms=start_ms,
        end_ms=end_ms,
        dependencies=[],
    )


BUILDER = StoryBuilder()


# ===========================================================================
# Test Set 1: Vocabulary membership (unit tests, no pipeline needed)
# ===========================================================================

class TestActionEventsVocabulary:
    """Verify 'cycling' is in _ACTION_EVENTS after Phase 6D fix."""

    def test_cycling_is_in_action_events(self):
        """Phase 6D fix: 'cycling' must be recognized as an action."""
        assert "cycling" in _ACTION_EVENTS, (
            "'cycling' not found in StoryBuilder._ACTION_EVENTS — "
            "Phase 6D fix may not have been applied."
        )

    def test_action_events_still_contains_original_types(self):
        """Existing action event types must not have been removed."""
        required = {
            EventType.PERSON_WALKING,
            EventType.PERSON_RUNNING,
            EventType.PERSON_STANDING,
            EventType.PERSON_LOITERING,
            EventType.VEHICLE_APPROACHING,
            EventType.VEHICLE_RECEDING,
            EventType.VEHICLE_STATIONARY,
        }
        missing = required - _ACTION_EVENTS
        assert not missing, f"Existing action events removed: {missing}"

    def test_entry_events_unchanged(self):
        """_ENTRY_EVENTS must still contain person_entered_scene and object_appeared."""
        assert EventType.PERSON_ENTERED_SCENE in _ENTRY_EVENTS
        assert EventType.OBJECT_APPEARED in _ENTRY_EVENTS

    def test_exit_events_unchanged(self):
        """_EXIT_EVENTS must still contain person_left_scene and object_disappeared."""
        assert EventType.PERSON_LEFT_SCENE in _EXIT_EVENTS
        assert EventType.OBJECT_DISAPPEARED in _EXIT_EVENTS

    def test_cycling_emitted_string_matches_action_event_key(self):
        """
        ActivityClassifier returns label='cycling'.
        S07 Pass 7 emits event_type=activity.label = 'cycling'.
        Verify the literal string 'cycling' is in _ACTION_EVENTS.
        """
        # The exact string the narrative_builder emits:
        narrative_builder_event_type = "cycling"
        assert narrative_builder_event_type in _ACTION_EVENTS


# ===========================================================================
# Test Set 2: entry+cycling+exit → COMPLETE
# ===========================================================================

class TestCyclingCompleteness:
    """
    The canonical chain found in Phase 6C/6D real footage:
        person_entered_scene → cycling → person_left_scene
    must produce StoryCompleteness.COMPLETE after Phase 6D fix.
    """

    def test_entry_cycling_exit_is_complete(self):
        """Core hypothesis: entry + cycling + exit → COMPLETE."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("cycling", start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert len(result.segments) == 1
        seg = result.segments[0]
        assert seg.completeness == StoryCompleteness.COMPLETE, (
            f"Expected COMPLETE, got {seg.completeness}. "
            f"event_types={seg.event_types}"
        )

    def test_entry_cycling_exit_counted_in_complete_segments(self):
        """complete_segments counter must be 1 for this chain."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("cycling", start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 1

    def test_entry_cycling_exit_with_high_narrative_score(self):
        """A COMPLETE segment must have higher narrative_score than PARTIAL."""
        complete_events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("cycling", start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        partial_events = [
            _evt(EventType.PERSON_ENTERED_SCENE, track_id=2, start_ms=0.0, end_ms=500.0),
            _evt(EventType.PERSON_LEFT_SCENE, track_id=2, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(complete_events + partial_events)
        segs_by_completeness = {s.completeness: s for s in result.segments}
        complete_seg = segs_by_completeness.get(StoryCompleteness.COMPLETE)
        partial_seg = segs_by_completeness.get(StoryCompleteness.PARTIAL)
        assert complete_seg is not None
        assert partial_seg is not None
        assert complete_seg.narrative_score > partial_seg.narrative_score, (
            f"COMPLETE score {complete_seg.narrative_score:.3f} not > "
            f"PARTIAL score {partial_seg.narrative_score:.3f}"
        )

    def test_cycling_only_is_minimal(self):
        """A single cycling event with no entry/exit is MINIMAL."""
        events = [_evt("cycling", start_ms=0.0, end_ms=5000.0)]
        result = BUILDER.build(events)
        assert result.complete_segments == 0
        assert result.segments[0].completeness == StoryCompleteness.MINIMAL

    def test_cycling_plus_entry_only_is_entry_only(self):
        """Entry + cycling (no exit) must NOT be COMPLETE."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("cycling", start_ms=1000.0, end_ms=5000.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 0
        assert result.segments[0].completeness != StoryCompleteness.COMPLETE

    def test_cycling_plus_exit_only_is_not_complete(self):
        """Cycling + exit (no entry) must NOT be COMPLETE."""
        events = [
            _evt("cycling", start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 0

    def test_multiple_cycling_events_same_track_still_complete(self):
        """Multiple cycling events on the same track: still COMPLETE."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("cycling", start_ms=1000.0, end_ms=5000.0),
            _evt("cycling", start_ms=5500.0, end_ms=9000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=10000.0, end_ms=10500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 1
        assert result.segments[0].completeness == StoryCompleteness.COMPLETE


# ===========================================================================
# Test Set 3: Existing COMPLETE behavior unchanged
# ===========================================================================

class TestExistingCompleteBehaviorUnchanged:
    """Non-cycling COMPLETE stories must still work."""

    def test_walking_entry_exit_is_complete(self):
        """Original action: person_walking — must still produce COMPLETE."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt(EventType.PERSON_WALKING, start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 1
        assert result.segments[0].completeness == StoryCompleteness.COMPLETE

    def test_running_entry_exit_is_complete(self):
        """Original action: person_running — must still produce COMPLETE."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt(EventType.PERSON_RUNNING, start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 1

    def test_standing_entry_exit_is_complete(self):
        """Original action: person_standing — must still produce COMPLETE."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt(EventType.PERSON_STANDING, start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 1


# ===========================================================================
# Test Set 4: Unroled events still do NOT produce COMPLETE
# ===========================================================================

class TestUnroledEventsStillPartial:
    """
    Events that are NOT in _ACTION_EVENTS must still produce PARTIAL,
    not COMPLETE. The fix is strictly additive.
    """

    def test_light_turned_on_not_an_action(self):
        """light_turned_on is an unroled event — entry+it+exit should be PARTIAL."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("light_turned_on", start_ms=1000.0, end_ms=2000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 0

    def test_person_reaching_up_not_an_action(self):
        """person_reaching_up is unroled — must not produce COMPLETE."""
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("person_reaching_up", start_ms=1000.0, end_ms=2000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        assert result.complete_segments == 0

    def test_narrative_running_string_now_an_action(self):
        """
        Phase 6D.4 fix: narrative_builder emits 'running' (not 'person_running').
        Phase 6D.4 added 'running' to _ACTION_EVENTS.
        entry + 'running' + exit is now COMPLETE.

        Previously (Phase 6D): asserted complete_segments == 0 (known defect).
        Phase 6D.4: this is the correct behavior — complete_segments == 1.
        """
        events = [
            _evt(EventType.PERSON_ENTERED_SCENE, start_ms=0.0, end_ms=500.0),
            _evt("running", start_ms=1000.0, end_ms=5000.0),
            _evt(EventType.PERSON_LEFT_SCENE, start_ms=6000.0, end_ms=6500.0),
        ]
        result = BUILDER.build(events)
        # Phase 6D.4: "running" IS in _ACTION_EVENTS — story should be COMPLETE
        assert result.complete_segments == 1, (
            "Phase 6D.4: 'running' is now in _ACTION_EVENTS. "
            "entry+running+exit should produce a COMPLETE story."
        )
