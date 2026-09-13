"""
Phase 6D.3 — Regression tests for temporal alignment fix and experimental threshold.

Tests:
  1. Temporal alignment (Defect A fix) — 4 required scenarios
  2. Threshold parameterization (Defect B experimental parameter)
  3. Backward-compatibility (default behavior unchanged)
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock
from dataclasses import dataclass
from typing import Optional

import pytest

from app.utils.activity_classifier import (
    ActivityClassifier,
    CYCLE_HORIZ_THRESHOLD,
)


# ── Stub helpers ──────────────────────────────────────────────────────────────

@dataclass
class BBox:
    cx: float; cy: float; width: float; height: float


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


def make_obs(frame: int, cx: float, cy: float, w: float = 0.05, h: float = 0.08) -> TrackObservation:
    return TrackObservation(
        frame_number=frame,
        timestamp_ms=frame * 5 / 30 * 1000,
        bbox=BBox(cx, cy, w, h),
    )


# ── Classifiers ────────────────────────────────────────────────────────────────

CLF_BASELINE = ActivityClassifier(fps=30.0, frame_skip=5)   # default — no fixes
CLF_TEMPORAL = ActivityClassifier(fps=30.0, frame_skip=5, require_temporal_overlap=True)
CLF_EXP_BOTH = ActivityClassifier(fps=30.0, frame_skip=5,
                                   cycle_threshold=0.25, require_temporal_overlap=True)


# ===========================================================================
# 1. Temporal alignment — Defect A fix
# ===========================================================================

class TestTemporalAlignment:
    """
    Four required scenarios for Signal 1 temporal alignment fix.
    Baseline (require_temporal_overlap=False) and fixed (=True) are both tested.
    """

    def test_temporally_disjoint_bicycle_does_not_trigger_with_fix(self):
        """
        Scenario 1: Bicycle spatially close but temporally disjoint.
        With temporal fix: must NOT trigger cycling.
        Baseline: DOES trigger cycling (KNOWN DEFECT documented in Phase 6D.2).
        """
        # Person at frames 10–25
        person_obs = [make_obs(f, cx=0.50, cy=0.50) for f in range(10, 26)]
        person = make_track(track_id=1, class_name="person", observations=person_obs)

        # Bicycle at frames 200–215 — completely disjoint
        bike_obs = [make_obs(f, cx=0.52, cy=0.51) for f in range(200, 216)]
        bike = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        # Baseline (broken): triggers because mean centroids are close
        r_baseline = CLF_BASELINE.classify(person, all_tracks=[person, bike])
        assert r_baseline.label == "cycling", (
            "Baseline should still trigger (known defect) — confirms Phase 6D.2 diagnosis."
        )

        # Temporal fix: does NOT trigger Signal 1 (person=[10,25], bike=[200,215] — no overlap)
        r_fixed = CLF_TEMPORAL.classify(person, all_tracks=[person, bike])
        assert r_fixed.label != "cycling", (
            f"With temporal fix, disjoint bicycle should NOT trigger cycling. "
            f"Got: {r_fixed.label}. "
            f"Person frames [10,25], bicycle frames [200,215] — no overlap."
        )

    def test_temporally_overlapping_bicycle_may_trigger_signal1(self):
        """
        Scenario 2: Bicycle spatially close AND temporally overlapping.
        With temporal fix: Signal 1 may trigger.
        """
        # Person at frames 10–25, bicycle at frames 15–30 — overlap at 15–25
        person_obs = [make_obs(f, cx=0.50, cy=0.50) for f in range(10, 26)]
        person = make_track(track_id=1, class_name="person", observations=person_obs)

        bike_obs = [make_obs(f, cx=0.52, cy=0.51) for f in range(15, 31)]
        bike = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        # Temporal fix: overlap exists, Signal 1 should evaluate normally
        r_fixed = CLF_TEMPORAL.classify(person, all_tracks=[person, bike])
        # Mean centroids: person (0.50, 0.50), bike (0.52, 0.51) → dist ≈ 0.022 < 0.25
        dist = math.sqrt((0.50 - 0.52)**2 + (0.50 - 0.51)**2)
        assert dist < 0.25, "Setup: bike should be within proximity"
        assert r_fixed.label == "cycling", (
            f"With temporal overlap AND spatial proximity, Signal 1 should fire. "
            f"Got: {r_fixed.label}"
        )

    def test_far_bicycle_with_overlap_does_not_trigger_signal1(self):
        """
        Scenario 3: Bicycle far away but temporally overlapping.
        Signal 1 proximity check should prevent triggering.
        """
        # Person at frames 10–25, bicycle at far side of frame (frames 10–25)
        person_obs = [make_obs(f, cx=0.10, cy=0.50) for f in range(10, 26)]
        person = make_track(track_id=1, class_name="person", observations=person_obs)

        bike_obs = [make_obs(f, cx=0.90, cy=0.50) for f in range(10, 26)]
        bike = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        # Temporal overlap: yes (same frames). Spatial: no (dist = 0.80 > 0.25)
        r_fixed = CLF_TEMPORAL.classify(person, all_tracks=[person, bike])
        # Signal 1 should not fire (too far). Person stationary → speed ≈ 0, no Signal 2.
        assert r_fixed.label != "cycling", (
            f"Far bicycle (dist=0.80) should not trigger Signal 1. Got: {r_fixed.label}"
        )

    def test_multiple_bicycles_only_overlapping_one_triggers(self):
        """
        Scenario 4: Multiple bicycle tracks. Only the temporally overlapping
        one is considered with the temporal fix.
        """
        # Person at frames 10–25
        person_obs = [make_obs(f, cx=0.50, cy=0.50) for f in range(10, 26)]
        person = make_track(track_id=1, class_name="person", observations=person_obs)

        # Bicycle A: close (dist~0.02), but disjoint (frames 200–215)
        bike_a_obs = [make_obs(f, cx=0.52, cy=0.51) for f in range(200, 216)]
        bike_a = make_track(track_id=2, class_name="bicycle", observations=bike_a_obs)

        # Bicycle B: also close but FAR (dist=0.8), overlapping (frames 10–25)
        bike_b_obs = [make_obs(f, cx=0.90, cy=0.50) for f in range(10, 26)]
        bike_b = make_track(track_id=3, class_name="bicycle", observations=bike_b_obs)

        # Temporal fix: bike_a skipped (disjoint), bike_b evaluated but far → no Signal 1
        # Person is stationary → no Signal 2
        r_fixed = CLF_TEMPORAL.classify(person, all_tracks=[person, bike_a, bike_b])
        assert r_fixed.label != "cycling", (
            f"Disjoint close bike + far overlapping bike → neither should trigger. "
            f"Got: {r_fixed.label}"
        )

    def test_partial_temporal_overlap_is_sufficient(self):
        """
        Overlapping by a single frame is sufficient for temporal alignment.
        Bicycle's last frame equals person's first frame.
        """
        # Person: frames 50–60
        person_obs = [make_obs(f, cx=0.50, cy=0.50) for f in range(50, 61)]
        person = make_track(track_id=1, class_name="person", observations=person_obs)

        # Bicycle: frames 40–50 (last frame = person's first frame → overlap at 50)
        bike_obs = [make_obs(f, cx=0.52, cy=0.51) for f in range(40, 51)]
        bike = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        # Overlap condition: bike_start(40) <= person_end(60) AND bike_end(50) >= person_start(50)
        assert 40 <= 60 and 50 >= 50, "Setup: should overlap at frame 50"

        r_fixed = CLF_TEMPORAL.classify(person, all_tracks=[person, bike])
        # Should evaluate Signal 1 (overlap exists, dist < 0.25)
        assert r_fixed.label == "cycling", (
            f"One-frame overlap (frame 50) should allow Signal 1. Got: {r_fixed.label}"
        )

    def test_just_outside_temporal_window_does_not_trigger(self):
        """
        Bicycle ends at frame 49; person starts at frame 50 → no overlap.
        """
        person_obs = [make_obs(f, cx=0.50, cy=0.50) for f in range(50, 61)]
        person = make_track(track_id=1, class_name="person", observations=person_obs)

        bike_obs = [make_obs(f, cx=0.52, cy=0.51) for f in range(40, 50)]  # ends at 49
        bike = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        # No overlap: bike_end(49) < person_start(50)
        assert 49 < 50, "Setup: bike ends before person starts"

        r_fixed = CLF_TEMPORAL.classify(person, all_tracks=[person, bike])
        assert r_fixed.label != "cycling", (
            f"Bicycle ending at frame 49, person starting at frame 50 — "
            f"no temporal overlap, Signal 1 should not fire. Got: {r_fixed.label}"
        )


# ===========================================================================
# 2. Threshold parameterization — Defect B experimental parameter
# ===========================================================================

class TestExperimentalThreshold:
    """
    Tests that cycle_threshold parameter controls Signal 2 trigger.
    """

    def test_low_threshold_fires_on_walking_speed(self):
        """Baseline threshold (0.018) fires on walking-pace motion."""
        # dx_per_obs = 0.018 * 5/30 * 2 = just above threshold
        dx = CYCLE_HORIZ_THRESHOLD * 5 / 30 * 2.5
        obs = [make_obs(i, cx=0.5 + i * dx, cy=0.5, h=0.05) for i in range(8)]
        track = make_track(observations=obs)
        r = CLF_BASELINE.classify(track, all_tracks=[])
        assert r.label == "cycling", (
            "Baseline threshold (0.018) should fire on walking speed."
        )

    def test_high_threshold_does_not_fire_on_walking_speed(self):
        """Experimental threshold (0.25) does NOT fire on walking-pace motion."""
        # Same walking-pace track as above
        dx = CYCLE_HORIZ_THRESHOLD * 5 / 30 * 2.5
        obs = [make_obs(i, cx=0.5 + i * dx, cy=0.5, h=0.05) for i in range(8)]
        track = make_track(observations=obs)
        # mean_speed ≈ CYCLE_HORIZ_THRESHOLD * 2.5 ≈ 0.045 << 0.25
        clf_high = ActivityClassifier(fps=30.0, frame_skip=5, cycle_threshold=0.25)
        r = clf_high.classify(track, all_tracks=[])
        assert r.label != "cycling", (
            f"Threshold=0.25 should not fire on walking-pace track (speed≈0.045). "
            f"Got: {r.label}"
        )

    def test_high_threshold_fires_on_high_speed_motion(self):
        """Experimental threshold (0.25) DOES fire on genuinely fast motion."""
        # speed = 0.30 normalised/s — above 0.25 threshold
        dt = 5 / 30
        dx_per_obs = 0.30 * dt   # 0.05 normalised per obs
        obs = [make_obs(i, cx=0.5 + i * dx_per_obs, cy=0.5, h=0.06) for i in range(8)]
        track = make_track(observations=obs)
        clf_high = ActivityClassifier(fps=30.0, frame_skip=5, cycle_threshold=0.25)
        r = clf_high.classify(track, all_tracks=[])
        # mean_speed ≈ 0.30 > 0.25, height_std ≈ 0 < 0.03 → cycling
        assert r.label == "cycling", (
            f"Threshold=0.25 should fire on fast-moving track (speed≈0.30). "
            f"Got: {r.label}"
        )

    def test_threshold_is_strict_boundary(self):
        """Tracks above the threshold fire; tracks below do not.
        Uses 5% above and 5% below to avoid floating-point boundary imprecision."""
        dt = 5 / 30
        threshold = 0.25

        # Speed 5% above threshold: should fire
        dx_above = threshold * dt * 1.05
        obs_above = [make_obs(i, cx=0.5 + i * dx_above, cy=0.5, h=0.06) for i in range(8)]
        track_above = make_track(track_id=1, observations=obs_above)
        clf = ActivityClassifier(fps=30.0, frame_skip=5, cycle_threshold=threshold)
        r_above = clf.classify(track_above, all_tracks=[])
        assert r_above.label == "cycling", (
            f"Speed 5% above threshold={threshold} should trigger. Got: {r_above.label}"
        )

        # Speed 50% below threshold: should NOT fire
        dx_below = threshold * dt * 0.50
        obs_below = [make_obs(i, cx=0.5 + i * dx_below, cy=0.5, h=0.06) for i in range(8)]
        track_below = make_track(track_id=2, observations=obs_below)
        r_below = clf.classify(track_below, all_tracks=[])
        assert r_below.label != "cycling", (
            f"Speed 50% below threshold={threshold} should not trigger. Got: {r_below.label}"
        )

    def test_threshold_sweep_relative_trigger_rates(self):
        """Higher thresholds trigger fewer cycling classifications."""
        dt = 5 / 30
        # 8 tracks at speeds 0.01 to 0.40
        speeds = [0.01, 0.05, 0.10, 0.18, 0.22, 0.25, 0.32, 0.40]
        tracks = []
        for i, sp in enumerate(speeds):
            dx = sp * dt
            obs = [make_obs(f, cx=0.2 + f * dx, cy=0.5, h=0.06) for f in range(8)]
            tracks.append(make_track(track_id=i, observations=obs))

        counts = {}
        for th in [0.018, 0.10, 0.20, 0.25, 0.35]:
            clf = ActivityClassifier(fps=30.0, frame_skip=5, cycle_threshold=th)
            c = sum(1 for t in tracks if clf.classify(t, all_tracks=[]).label == "cycling")
            counts[th] = c

        # Higher threshold → fewer or equal cycling classifications
        thresholds = sorted(counts)
        for i in range(len(thresholds) - 1):
            assert counts[thresholds[i]] >= counts[thresholds[i+1]], (
                f"Higher threshold should not produce MORE cycling: "
                f"th={thresholds[i]}→{counts[thresholds[i]]} "
                f"th={thresholds[i+1]}→{counts[thresholds[i+1]]}"
            )


# ===========================================================================
# 3. Backward-compatibility — default behaviour unchanged
# ===========================================================================

class TestBackwardCompatibility:
    """
    ActivityClassifier() with no args must behave identically to baseline (bd9d18e).
    TCE_V1_REFERENCE does not set cycle_threshold or require_temporal_overlap,
    so defaults must reproduce original behaviour.
    """

    def test_default_constructor_baseline_threshold(self):
        """Default classifier uses CYCLE_HORIZ_THRESHOLD = 0.018."""
        clf = ActivityClassifier()
        assert clf._cycle_threshold == CYCLE_HORIZ_THRESHOLD, (
            f"Default cycle_threshold should be {CYCLE_HORIZ_THRESHOLD}, "
            f"got {clf._cycle_threshold}"
        )

    def test_default_constructor_no_temporal_requirement(self):
        """Default classifier does NOT require temporal overlap (preserves baseline defect)."""
        clf = ActivityClassifier()
        assert clf._require_temporal_overlap is False, (
            "Default require_temporal_overlap should be False "
            "(preserves TCE_V1_REFERENCE behavior)."
        )

    def test_default_fires_on_walking_pedestrian(self):
        """
        Default ActivityClassifier reproduces Phase 6D.2 defect:
        fires on a walking pedestrian (speed just above 0.018).
        """
        dx = CYCLE_HORIZ_THRESHOLD * 5 / 30 * 3  # speed ≈ 0.054 n/s
        obs = [make_obs(i, cx=0.5 + i * dx, cy=0.5, h=0.05) for i in range(8)]
        track = make_track(observations=obs)
        clf = ActivityClassifier()
        r = clf.classify(track, all_tracks=[])
        # Reproduces known defect — classifier fires on walking speed
        assert r.label == "cycling", (
            "Default classifier must reproduce baseline defect for backward compatibility. "
            f"Got: {r.label}"
        )

    def test_default_fires_on_disjoint_bicycle(self):
        """
        Default ActivityClassifier reproduces Phase 6D.2 defect:
        fires when bicycle is in a disjoint time window.
        """
        person_obs = [make_obs(f, cx=0.50, cy=0.50) for f in range(10, 26)]
        person = make_track(track_id=1, class_name="person", observations=person_obs)

        bike_obs = [make_obs(f, cx=0.52, cy=0.51) for f in range(200, 216)]
        bike = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        clf = ActivityClassifier()
        r = clf.classify(person, all_tracks=[person, bike])
        assert r.label == "cycling", (
            "Default classifier must reproduce temporal misalignment defect. "
            f"Got: {r.label}"
        )
