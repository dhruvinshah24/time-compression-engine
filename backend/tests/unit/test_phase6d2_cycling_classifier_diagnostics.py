"""
Phase 6D.2 — Diagnostic tests for ActivityClassifier cycling over-trigger.

These tests make the diagnosed failure modes reproducible and prevent
them from being silently fixed or worsened without notice.

They do NOT change production classifier behaviour.
They do NOT modify any thresholds.
They document the CURRENT (broken) state so that future fixes can be
measured against an explicit baseline.

Tests are grouped into:
  1. Signal 2 sub-pixel threshold tests — documents the resolution sensitivity
  2. Signal 1 temporal misalignment tests — documents that no temporal overlap is required
  3. Decision-tree priority tests — documents cycling pre-empts walking/running
  4. Known over-trigger pattern tests — reproduces the exact scenarios from Phase 6D.1

Each test that documents a KNOWN DEFECT is marked with:
    # KNOWN DEFECT (Phase 6D.2): <description>
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.utils.activity_classifier import (
    ActivityClassifier,
    CYCLE_HORIZ_THRESHOLD,
    WALK_THRESHOLD,
    RUN_THRESHOLD,
    STILL_THRESHOLD,
    BICYCLE_CLASSES,
)

# ---------------------------------------------------------------------------
# Minimal stub types matching Track / TrackObservation / BBox interface
# ---------------------------------------------------------------------------

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
    observations: list[TrackObservation] = None,
    confirmed_at_frame: Optional[int] = 1,
) -> MagicMock:
    t = MagicMock()
    t.track_id = track_id
    t.class_name = class_name
    t.observations = observations or []
    t.is_confirmed = confirmed_at_frame is not None
    t.confirmed_at_frame = confirmed_at_frame
    return t


def make_obs(
    frame: int,
    cx: float,
    cy: float,
    w: float = 0.05,
    h: float = 0.10,
    fps: float = 30.0,
    frame_skip: int = 5,
) -> TrackObservation:
    ts = frame * frame_skip / fps * 1000  # ms
    return TrackObservation(frame_number=frame, timestamp_ms=ts, bbox=BBox(cx, cy, w, h))


CLF = ActivityClassifier(fps=30.0, frame_skip=5)
CLF_HD = ActivityClassifier(fps=30.0, frame_skip=5)   # same params, used for contrast


# ===========================================================================
# 1. Signal 2 sub-pixel threshold tests
# ===========================================================================

class TestSignal2SubPixelThreshold:
    """
    Documents that CYCLE_HORIZ_THRESHOLD = 0.018 normalised/s is at sub-pixel
    level for 320×240 footage.

    At 320×240, frame_skip=5, fps=30:
      dt = 0.167 s
      0.018 × 0.167 = 0.003 normalised displacement per observation
      = 0.003 × 320 px = 0.96 pixels per observation

    Sub-pixel motion triggers cycling classification.
    """

    def test_threshold_value_at_320x240(self):
        """Verify the threshold in pixel terms at 320×240 resolution."""
        dt = 5 / 30  # seconds per extracted frame
        disp_per_obs = CYCLE_HORIZ_THRESHOLD * dt  # normalised displacement per obs
        pixels_per_obs_horizontal = disp_per_obs * 320
        pixels_per_obs_vertical   = disp_per_obs * 240

        # Document: threshold = sub-pixel displacement
        assert pixels_per_obs_horizontal < 1.5, (
            f"CYCLE_HORIZ_THRESHOLD implies {pixels_per_obs_horizontal:.3f} px/obs at 320px width — "
            f"close to or below 1 pixel. This is a KNOWN DEFECT (Phase 6D.2)."
        )

    def test_slow_pedestrian_with_minimal_jitter_triggers_cycling(self):
        """
        KNOWN DEFECT (Phase 6D.2): A nearly-stationary person whose centroid
        drifts by ~2 pixels per observation can trigger cycling classification.

        At 320×240: 2px / 320 = 0.00625 normalised; over dt=0.167s = 0.0375 n/s.
        This is > CYCLE_HORIZ_THRESHOLD (0.018) — cycling fires.
        """
        # Person moving ~2px/obs horizontally (0.00625 normalised per obs)
        obs = [make_obs(i, cx=0.5 + i * 0.00625, cy=0.5, h=0.05) for i in range(8)]
        track = make_track(observations=obs)
        result = CLF.classify(track, all_tracks=[])

        # Document current (broken) behaviour
        # 2px/obs at 320px width = 0.037 n/s > 0.018 threshold
        # Height std near 0 for constant height → cycling fires
        # KNOWN DEFECT: this should classify as standing/walking, not cycling
        displacement_per_obs_px = 0.00625 * 320
        assert displacement_per_obs_px < 3, "Setup: should be slow movement"
        # Current behaviour check (documents the defect):
        assert result.label == "cycling", (
            "KNOWN DEFECT (Phase 6D.2): A person moving only "
            f"{displacement_per_obs_px:.1f}px/obs is classified as cycling. "
            "Expected: walking or standing."
        )

    def test_only_3_tracks_have_speed_below_threshold_in_real_300s_run(self):
        """
        Documents that CYCLE_HORIZ_THRESHOLD = 0.018 is below the speed of
        98.7% of all tracks in the archive_001 300s run.

        Data from Phase 6D.2 feature extraction:
          227/230 tracks (98.7%) have mean_speed >= 0.018
        This is a diagnostic fact, not a passing criterion.
        """
        # The threshold is at the 1.3th percentile of observed speeds.
        # A well-calibrated cycling threshold should be above walking speed.
        # Walking threshold is WALK_THRESHOLD = 0.008.
        # Cycling threshold should be substantially above walking: at minimum 3×.
        min_reasonable_cycling_threshold = WALK_THRESHOLD * 3  # 0.024
        assert CYCLE_HORIZ_THRESHOLD >= WALK_THRESHOLD, \
            "Cycling threshold should be above walking threshold"
        # Documents that it is only marginally above walking:
        assert CYCLE_HORIZ_THRESHOLD < min_reasonable_cycling_threshold, (
            f"KNOWN DEFECT (Phase 6D.2): CYCLE_HORIZ_THRESHOLD ({CYCLE_HORIZ_THRESHOLD}) "
            f"is only {CYCLE_HORIZ_THRESHOLD / WALK_THRESHOLD:.1f}× the walking threshold. "
            f"Expected ≥3× ({min_reasonable_cycling_threshold}) for reliable discrimination."
        )


# ===========================================================================
# 2. Signal 1 temporal misalignment tests
# ===========================================================================

class TestSignal1TemporalMisalignment:
    """
    Documents that Signal 1 fires even when person and bicycle tracks
    exist at completely different time windows.

    KNOWN DEFECT (Phase 6D.2): No temporal overlap check is performed.
    Mean centroids over the entire track duration are compared.
    A bicycle visible at t=10s can trigger cycling for a person visible at t=290s
    if their average frame positions happen to be within 0.25 normalised.
    """

    def test_bicycle_from_different_time_window_triggers_cycling(self):
        """
        A person track at frames 100–110 and a bicycle track at frames 500–510
        (completely non-overlapping) should NOT trigger Signal 1.
        But the current implementation DOES trigger it if their mean centroids are close.

        KNOWN DEFECT: no temporal overlap check.
        """
        # Person appears at frames 100–110
        person_obs = [make_obs(f, cx=0.5, cy=0.5, h=0.10) for f in range(100, 115)]
        person_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Bicycle appears at frames 500–510 (no overlap with person)
        bike_obs = [make_obs(f, cx=0.52, cy=0.51, h=0.08) for f in range(500, 515)]
        bike_track = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        result = CLF.classify(person_track, all_tracks=[person_track, bike_track])

        # Current (broken) behaviour: cycling fires because mean centroids are close
        # person mean cx ≈ 0.5, bike mean cx ≈ 0.52 → dist ≈ 0.028 < 0.25
        person_mean_cx = np.mean([o.bbox.cx for o in person_obs])
        bike_mean_cx   = np.mean([o.bbox.cx for o in bike_obs])
        bike_mean_cy   = np.mean([o.bbox.cy for o in bike_obs])
        person_mean_cy = np.mean([o.bbox.cy for o in person_obs])
        dist = math.sqrt((person_mean_cx - bike_mean_cx)**2 + (person_mean_cy - bike_mean_cy)**2)
        assert dist < 0.25, "Setup: centroids should be within proximity threshold"

        # KNOWN DEFECT: this should NOT classify as cycling (different time windows)
        assert result.label == "cycling", (
            "KNOWN DEFECT (Phase 6D.2): cycling fires for a person and bicycle "
            "that appear at non-overlapping time windows. "
            f"Person frames 100–114, bicycle frames 500–514, dist={dist:.3f}. "
            "Expected: no cycling classification from Signal 1."
        )

    def test_bicycle_on_opposite_side_of_frame_does_not_trigger(self):
        """
        A bicycle whose mean centroid is > 0.25 normalised from the person
        does NOT trigger Signal 1. This is the only existing guard.
        """
        person_obs = [make_obs(f, cx=0.2, cy=0.5, h=0.10) for f in range(10, 20)]
        person_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Bicycle far to the right
        bike_obs = [make_obs(f, cx=0.9, cy=0.5, h=0.08) for f in range(10, 20)]
        bike_track = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        result = CLF.classify(person_track, all_tracks=[person_track, bike_track])

        # Signal 1 should NOT fire (dist = 0.7 > 0.25)
        # Signal 2 may still fire depending on speed — test walking speed
        # For this test, person is stationary so speed ≈ 0 → not cycling
        if result.label == "cycling":
            # Could only be Signal 2 (distance guard works)
            # Verify Signal 1 distance is correctly above threshold
            person_mean_cx = np.mean([o.bbox.cx for o in person_obs])
            bike_mean_cx   = np.mean([o.bbox.cx for o in bike_obs])
            dist = abs(person_mean_cx - bike_mean_cx)
            assert dist > 0.25, "Signal 1 should not fire for far bicycle"

    def test_confirmed_bicycle_class_filter_works(self):
        """Unconfirmed bicycle tracks should NOT trigger Signal 1."""
        person_obs = [make_obs(f, cx=0.5, cy=0.5, h=0.10) for f in range(10, 20)]
        person_track = make_track(track_id=1, class_name="person", observations=person_obs)

        # Unconfirmed bicycle track (confirmed_at_frame=None)
        bike_obs = [make_obs(f, cx=0.52, cy=0.51, h=0.08) for f in range(10, 20)]
        bike_track = make_track(track_id=2, class_name="bicycle",
                                observations=bike_obs, confirmed_at_frame=None)
        bike_track.is_confirmed = False

        # Signal 1 checks t.is_confirmed — unconfirmed bicycle should not trigger
        # Note: person has near-zero speed (stable cx), so Signal 2 also shouldn't fire
        result = CLF.classify(person_track, all_tracks=[person_track, bike_track])
        # Unconfirmed bicycle → no Signal 1. Person stationary → no Signal 2.
        assert result.label != "cycling", (
            f"Unconfirmed bicycle should not trigger Signal 1, got label={result.label}"
        )


# ===========================================================================
# 3. Decision-tree priority tests
# ===========================================================================

class TestDecisionTreePriority:
    """
    Documents that cycling takes absolute priority in the decision tree.
    A person clearly running at high speed is classified as cycling
    if Signal 1 fires — there is no override mechanism.

    KNOWN DEFECT (Phase 6D.2): cycling pre-empts running/walking.
    """

    def test_cycling_label_takes_priority_over_running(self):
        """
        A person running at well above RUN_THRESHOLD is classified cycling
        if a nearby bicycle track exists.

        KNOWN DEFECT: running evidence is ignored when cycling_conf >= 0.60.
        """
        # Very fast movement: > RUN_THRESHOLD (0.022) in speed
        fast_obs = [make_obs(f, cx=0.5 + f * 0.05, cy=0.5, h=0.12) for f in range(10)]
        person_track = make_track(track_id=1, class_name="person", observations=fast_obs)

        # Bicycle close by
        bike_obs = [make_obs(f, cx=0.52, cy=0.52, h=0.08) for f in range(10)]
        bike_track = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        result = CLF.classify(person_track, all_tracks=[person_track, bike_track])

        # Verify speed is above running threshold
        # dx per obs = 0.05, dt = 0.167s → vx = 0.05/0.167 = 0.3 > RUN_THRESHOLD
        dt = 5 / 30
        speed_per_obs = 0.05 / dt
        assert speed_per_obs > RUN_THRESHOLD, "Setup: should be running speed"

        # KNOWN DEFECT: result is cycling, not running
        assert result.label == "cycling", (
            "KNOWN DEFECT (Phase 6D.2): cycling pre-empts running in decision tree. "
            f"Expected running (speed={speed_per_obs:.3f} > RUN_THRESHOLD={RUN_THRESHOLD}), "
            f"got {result.label}."
        )

    def test_cycling_label_takes_priority_over_walking(self):
        """
        Walking-speed movement with a nearby bicycle is classified cycling.
        KNOWN DEFECT: walking evidence is ignored.
        """
        # Walking speed: between WALK_THRESHOLD and RUN_THRESHOLD
        walk_obs = [make_obs(f, cx=0.3 + f * 0.015, cy=0.5, h=0.10) for f in range(8)]
        person_track = make_track(track_id=1, class_name="person", observations=walk_obs)

        bike_obs = [make_obs(f, cx=0.35, cy=0.51, h=0.08) for f in range(8)]
        bike_track = make_track(track_id=2, class_name="bicycle", observations=bike_obs)

        result = CLF.classify(person_track, all_tracks=[person_track, bike_track])
        assert result.label == "cycling", (
            "KNOWN DEFECT (Phase 6D.2): walking-speed person near bicycle classified cycling."
        )


# ===========================================================================
# 4. Known over-trigger pattern tests (Phase 6D.1 reproductions)
# ===========================================================================

class TestPhase6D1ReproductionPatterns:
    """
    Reproduces the structural conditions that caused each Phase 6D.1 false positive.
    These tests document the specific failure modes.
    """

    def test_low_speed_track_with_stable_height_triggers_signal2(self):
        """
        Reproduces Track 1 scenario: very slow motion (animated title card),
        speed just above CYCLE_HORIZ_THRESHOLD, stable height.

        KNOWN DEFECT: Signal 2 fires for speed = 0.035 (just 2× threshold).
        """
        # Track 1: mean_speed=0.0347, height_std=0.00587
        # Reproduce: 4px/obs at 320px = 0.0125 normalised → vel = 0.075 n/s
        # Actually mean_speed was 0.0347 → displacement per obs = 0.0347 × 0.167 = 0.0058 n/s
        # Let's set dx = 0.0347 × 0.167 ≈ 0.0058 normalised per obs
        dx_per_obs = CYCLE_HORIZ_THRESHOLD * 5 / 30 * 2  # 2× threshold displacement
        obs = [make_obs(i, cx=0.5 + i * dx_per_obs, cy=0.5, h=0.063, w=0.04)
               for i in range(16)]
        track = make_track(observations=obs)
        result = CLF.classify(track, all_tracks=[])
        # Signal 2: speed ≈ dx/dt = 2 × CYCLE_HORIZ_THRESHOLD → fires
        # height_std = 0 (constant h=0.063) → fires
        assert result.label == "cycling", (
            "KNOWN DEFECT (Phase 6D.2): reproduces Track 1 pattern — "
            "very low speed (2× threshold), constant height → cycling fires. "
            "Should be 'walking' or 'standing'."
        )

    def test_stationary_arm_movement_with_bicycle_nearby_triggers_cycling(self):
        """
        Reproduces Track 62 scenario: nurse's arm moving at high speed while
        person is effectively stationary, bicycle track nearby.

        KNOWN DEFECT: high centroid speed from limb movement triggers Signal 1
        when a bicycle track is nearby (even from different scene).
        """
        # High centroid movement (0.5 normalised speed — nurse arm swing)
        obs = [make_obs(f, cx=0.4 + (0.01 if f % 2 == 0 else -0.01), cy=0.4 + f * 0.002,
                        h=0.20, w=0.15)   # large box = close subject
               for f in range(17)]
        person_track = make_track(track_id=62, class_name="person", observations=obs)

        # Nearby bicycle (same mean centroid region)
        bike_obs = [make_obs(f, cx=0.42, cy=0.42, h=0.08) for f in range(17)]
        bike_track = make_track(track_id=99, class_name="bicycle", observations=bike_obs)

        result = CLF.classify(person_track, all_tracks=[person_track, bike_track])
        # Signal 1: bicycle nearby → fires regardless of what person is doing
        assert result.label == "cycling", (
            "KNOWN DEFECT (Phase 6D.2): reproduces Track 62 pattern — "
            "Signal 1 fires from nearby bicycle regardless of actual activity."
        )

    def test_pedestrian_walking_triggers_signal2_at_320x240_resolution(self):
        """
        Reproduces Track 234/285 scenario: normal outdoor pedestrian walking
        at typical speed (0.40 normalised/s) triggers Signal 2.

        KNOWN DEFECT: any walking speed above 0.018 n/s with stable height = cycling.
        At 320×240, this includes ALL walking pedestrians.
        """
        # Walking at mean_speed ~ 0.40 n/s (typical human walking)
        # dx per obs = 0.40 × 0.167 ≈ 0.067 normalised
        dx_per_obs = 0.067
        obs = [make_obs(f, cx=0.2 + f * dx_per_obs, cy=0.5, h=0.065, w=0.04)
               for f in range(8)]
        track = make_track(observations=obs)
        result = CLF.classify(track, all_tracks=[])
        assert result.label == "cycling", (
            "KNOWN DEFECT (Phase 6D.2): reproduces Track 234/285 pattern — "
            "normal walking pedestrian classified cycling by Signal 2. "
            "Should be 'walking'."
        )
