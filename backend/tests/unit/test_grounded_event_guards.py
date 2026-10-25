"""
Tests for Grounded Event Verification Guards:
  1. Staircase presence gating in ActivityClassifier (prevents 2D perspective velocity from causing stair walking on flat ground).
  2. Physical elevation & stability check in InteractionDetector for person_drinking (prevents false drinking events when cups sit on desks).
  3. Minimum observation stability guard for person_picked_up_object in InteractionDetector (prevents false pickup on 2-frame detector flickers).
"""

from dataclasses import dataclass
from unittest.mock import MagicMock
import pytest

from app.utils.activity_classifier import (
    ActivityClassifier,
    STAIR_CLASSES,
)
from app.utils.interaction_detector import InteractionDetector


@dataclass
class BBox:
    cx: float
    cy: float
    width: float
    height: float

    @property
    def x1(self) -> float:
        return self.cx - self.width / 2.0

    @property
    def y1(self) -> float:
        return self.cy - self.height / 2.0

    @property
    def x2(self) -> float:
        return self.cx + self.width / 2.0

    @property
    def y2(self) -> float:
        return self.cy + self.height / 2.0


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


def make_stair_obs_series(n_obs: int, start_frame: int = 10) -> list[TrackObservation]:
    """Observations with vertical upward velocity at walking pace."""
    obs = []
    for i in range(n_obs):
        f = start_frame + i * 5
        cx = 0.3 + i * 0.001
        cy = 0.8 - i * 0.002  # cy decreasing = moving UP in image at normal walking pace
        # Natural gait height fluctuation (std >= 0.03) prevents seated cycling detection
        h = 0.15 + (0.04 if i % 2 == 0 else -0.04)
        obs.append(TrackObservation(
            frame_number=f,
            timestamp_ms=f * 5 / 30 * 1000,
            bbox=BBox(cx=cx, cy=cy, width=0.08, height=h),
        ))
    return obs


# ── 1. Staircase Presence Guard ────────────────────────────────────────────────

class TestStaircasePresenceGuard:
    """Verifies that flat-ground vertical locomotion is not labeled as stairs unless stairs exist."""

    def test_baseline_without_guard_classifies_vertical_velocity_as_stairs(self):
        clf = ActivityClassifier(require_staircase_for_stairs=False)
        person_track = make_track(track_id=1, class_name="person", observations=make_stair_obs_series(15))
        res = clf.classify(person_track, all_tracks=[person_track])
        assert res.label == "walking_upstairs"

    def test_guard_suppresses_stairs_to_walking_when_no_staircase_in_scene(self):
        clf = ActivityClassifier(require_staircase_for_stairs=True)
        person_track = make_track(track_id=1, class_name="person", observations=make_stair_obs_series(15))
        res = clf.classify(person_track, all_tracks=[person_track])
        assert res.label == "walking"
        assert res.evidence.get("stair_suppressed") is True
        assert res.evidence.get("stair_suppression_reason") == "no_staircase_in_scene"

    def test_guard_permits_stairs_when_confirmed_staircase_track_exists(self):
        clf = ActivityClassifier(require_staircase_for_stairs=True)
        person_track = make_track(track_id=1, class_name="person", observations=make_stair_obs_series(15))
        stair_track = make_track(track_id=99, class_name="stairs", observations=[TrackObservation(10, 0, BBox(0.3, 0.4, 0.4, 0.5))], confirmed=True)
        res = clf.classify(person_track, all_tracks=[person_track, stair_track])
        assert res.label == "walking_upstairs"


# ── 2. Drinking Elevation and Stability Guards ─────────────────────────────────

class TestDrinkingGuards:
    """Verifies that person_drinking requires stable tracks and physical elevation to head level."""

    def test_transient_object_flicker_does_not_trigger_drinking(self):
        detector = InteractionDetector(fps=30.0, frame_skip=5)
        # Person sitting/standing for 30 frames
        person_obs = [
            TrackObservation(f, f * 50, BBox(0.5, 0.5, 0.1, 0.3))
            for f in range(10, 40)
        ]
        p_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Bottle flickers for only 2 frames at head level
        bottle_obs = [
            TrackObservation(10, 500, BBox(0.5, 0.4, 0.03, 0.05)),
            TrackObservation(11, 550, BBox(0.5, 0.4, 0.03, 0.05)),
        ]
        bottle_track = make_track(track_id=2, class_name="bottle", observations=bottle_obs)

        events = detector.detect([p_track], [p_track, bottle_track])
        drinking_events = [e for e in events if e.event_type == "person_drinking"]
        assert len(drinking_events) == 0, "Transient 2-frame bottle detection should not trigger drinking"

    def test_table_level_cup_does_not_trigger_drinking(self):
        detector = InteractionDetector(fps=30.0, frame_skip=5)
        # Person from y1 = 0.35 to y2 = 0.65 (height = 0.30, head level <= 0.47)
        person_obs = [
            TrackObservation(f, f * 50, BBox(0.5, 0.5, 0.1, 0.3))
            for f in range(10, 30)
        ]
        p_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Cup sits on desk at y = 0.60 (near waist/desk level, below chest)
        cup_obs = [
            TrackObservation(f, f * 50, BBox(0.52, 0.60, 0.03, 0.05))
            for f in range(10, 30)
        ]
        cup_track = make_track(track_id=2, class_name="cup", observations=cup_obs)

        events = detector.detect([p_track], [p_track, cup_track])
        drinking_events = [e for e in events if e.event_type == "person_drinking"]
        assert len(drinking_events) == 0, "Desk-level cup must not trigger person_drinking"

    def test_elevated_container_at_mouth_level_triggers_drinking(self):
        detector = InteractionDetector(fps=30.0, frame_skip=5)
        # Person from y1 = 0.35 to y2 = 0.65 (head is at y=0.35-0.42)
        person_obs = [
            TrackObservation(f, f * 166.7, BBox(0.5, 0.5, 0.1, 0.3))
            for f in range(10, 25)
        ]
        p_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Cup held at head/mouth level y = 0.40 for 12 frames (>= 1.5s)
        cup_obs = [
            TrackObservation(f, f * 166.7, BBox(0.51, 0.40, 0.03, 0.05))
            for f in range(10, 22)
        ]
        cup_track = make_track(track_id=2, class_name="cup", observations=cup_obs)

        events = detector.detect([p_track], [p_track, cup_track])
        drinking_events = [e for e in events if e.event_type == "person_drinking"]
        assert len(drinking_events) == 1
        assert drinking_events[0].track_id == 1
        assert drinking_events[0].object_class == "cup"


# ── 3. Pickup Stability Guard ─────────────────────────────────────────────────

class TestPickupGuards:
    """Verifies that transient 2-frame dropped tracks do not trigger object pickup."""

    def test_transient_dropped_object_does_not_trigger_pickup(self):
        detector = InteractionDetector(fps=30.0, frame_skip=5)
        person_obs = [
            TrackObservation(f, f * 50, BBox(0.5, 0.5, 0.1, 0.3))
            for f in range(10, 50)
        ]
        p_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Cup detected for only 2 frames (flicker noise) then vanishes
        cup_obs = [
            TrackObservation(10, 500, BBox(0.52, 0.52, 0.03, 0.05)),
            TrackObservation(11, 550, BBox(0.52, 0.52, 0.03, 0.05)),
        ]
        cup_track = make_track(track_id=2, class_name="cup", observations=cup_obs)

        events = detector.detect([p_track], [p_track, cup_track])
        pickup_events = [e for e in events if "picked_up" in e.event_type]
        assert len(pickup_events) == 0, "2-frame flicker drop should not trigger person_picked_up_cup"

    def test_stable_object_disappearing_triggers_pickup(self):
        detector = InteractionDetector(fps=30.0, frame_skip=5)
        person_obs = [
            TrackObservation(f, f * 50, BBox(0.5, 0.5, 0.1, 0.3))
            for f in range(10, 50)
        ]
        p_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Stable cup on desk for 10 frames, then picked up and vanishes
        cup_obs = [
            TrackObservation(f, f * 50, BBox(0.52, 0.52, 0.03, 0.05))
            for f in range(10, 20)
        ]
        cup_track = make_track(track_id=2, class_name="cup", observations=cup_obs)

        events = detector.detect([p_track], [p_track, cup_track])
        pickup_events = [e for e in events if "picked_up" in e.event_type]
        assert len(pickup_events) == 1
        assert pickup_events[0].event_type == "person_picked_up_cup"
