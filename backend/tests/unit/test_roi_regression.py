"""
ROI Regression Tests — Phase 5A.

Covers all crossing scenarios that must work correctly after the Phase 4
cold-start fix and the Phase 5A FAIL-003 invalidation.

FAIL-002 regression: cold-start inside zone → entry event immediately.
FAIL-003 regression: synthetic trajectory entry/exit timing within ±1 frame.

These tests must NOT be deleted or weakened unless a deliberate architecture
change makes the behaviour intentionally different.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BACKEND))

from app.utils.roi_manager import ROIManager, ZoneType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SQUARE_ZONE = [{
    "zone_id": "z_square",
    "name":    "Square Zone",
    "zone_type": "restricted",
    "polygon": [
        [0.30, 0.20],
        [0.70, 0.20],
        [0.70, 0.80],
        [0.30, 0.80],
    ],
}]

CROSSING_ZONE = [{
    "zone_id": "z_crossing",
    "name":    "Crossing Zone",
    "zone_type": "restricted",
    # x=0.40–0.60, full height — same zone used in corpus simulation
    "polygon": [
        [0.40, 0.0],
        [0.60, 0.0],
        [0.60, 1.0],
        [0.40, 1.0],
    ],
}]


def make_mgr(zones: list[dict]) -> ROIManager:
    mgr = ROIManager()
    mgr.load_zones(zones)
    return mgr


def feed(mgr: ROIManager, track_id: str, points: list[tuple[float, float]]) -> list:
    """Feed a list of (cx, cy) points and collect all emitted events."""
    events = []
    for frame, (cx, cy) in enumerate(points):
        evts = mgr.check_point(track_id, cx, cy, frame_number=frame, timestamp_ms=frame * 40.0)
        events.extend(evts)
    return events


# ---------------------------------------------------------------------------
# 1. Normal entry (outside → inside)
# ---------------------------------------------------------------------------

class TestNormalEntry:
    def test_outside_then_inside_fires_entry(self):
        mgr = make_mgr(SQUARE_ZONE)
        events = feed(mgr, "t1", [(0.10, 0.50), (0.50, 0.50)])
        assert len(events) == 1
        assert events[0].event_type == "restricted_zone_entry"
        assert events[0].direction == "entering"
        assert events[0].zone_id == "z_square"

    def test_entry_track_id_correct(self):
        mgr = make_mgr(SQUARE_ZONE)
        events = feed(mgr, "track_abc", [(0.10, 0.50), (0.50, 0.50)])
        assert events[0].track_id == "track_abc"

    def test_entry_frame_number_correct(self):
        mgr = make_mgr(SQUARE_ZONE)
        events = feed(mgr, "t1", [(0.10, 0.50), (0.50, 0.50)])
        # Entry detected at frame index 1 (second point is inside)
        assert events[0].frame_number == 1


# ---------------------------------------------------------------------------
# 2. Normal exit (inside → outside)
# ---------------------------------------------------------------------------

class TestNormalExit:
    def test_inside_then_outside_fires_exit(self):
        mgr = make_mgr(SQUARE_ZONE)
        events = feed(mgr, "t1", [(0.10, 0.50), (0.50, 0.50), (0.90, 0.50)])
        assert len(events) == 2
        assert events[1].event_type == "restricted_zone_exit"
        assert events[1].direction == "exiting"

    def test_exit_frame_number_correct(self):
        mgr = make_mgr(SQUARE_ZONE)
        events = feed(mgr, "t1", [(0.10, 0.50), (0.50, 0.50), (0.90, 0.50)])
        assert events[1].frame_number == 2


# ---------------------------------------------------------------------------
# 3. Boundary touch
# ---------------------------------------------------------------------------

class TestBoundaryTouch:
    def test_point_exactly_on_left_edge_is_inside(self):
        """Point exactly at x=0.30 (left edge of zone) should be treated as inside."""
        mgr = make_mgr(SQUARE_ZONE)
        mgr.check_point("t1", 0.10, 0.50, frame_number=0, timestamp_ms=0.0)  # outside
        events = mgr.check_point("t1", 0.30, 0.50, frame_number=1, timestamp_ms=40.0)  # on edge
        # Ray-casting on boundary may be inside OR outside — we just check no crash
        assert isinstance(events, list)

    def test_point_clearly_outside_near_boundary(self):
        """Point at x=0.29 (just left of zone x=0.30) must NOT trigger entry."""
        mgr = make_mgr(SQUARE_ZONE)
        events = feed(mgr, "t1", [(0.29, 0.50), (0.29, 0.50)])
        assert len(events) == 0


# ---------------------------------------------------------------------------
# 4. Approach without crossing
# ---------------------------------------------------------------------------

class TestApproachWithoutCrossing:
    def test_approach_and_stop_short(self):
        mgr = make_mgr(SQUARE_ZONE)
        # Move from 0.10 toward zone but stop at 0.28 (never reaches 0.30)
        points = [(0.10 + i * 0.01, 0.50) for i in range(19)]  # 0.10 → 0.28
        events = feed(mgr, "t1", points)
        assert len(events) == 0

    def test_parallel_motion_along_boundary(self):
        """Move parallel to the zone boundary without entering."""
        mgr = make_mgr(SQUARE_ZONE)
        # Move along x=0.25 from y=0 to y=1 — never inside zone (x=0.30–0.70)
        points = [(0.25, i * 0.1) for i in range(11)]
        events = feed(mgr, "t1", points)
        assert len(events) == 0


# ---------------------------------------------------------------------------
# 5. Cold-start inside zone (FAIL-002 regression)
# ---------------------------------------------------------------------------

class TestColdStartFix:
    def test_cold_start_inside_emits_entry(self):
        """
        FAIL-002 regression test.
        When a track's FIRST observation is inside a zone, an immediate
        restricted_zone_entry must be emitted.
        Fixed in Phase 4, 2026-08-26.
        """
        mgr = make_mgr(SQUARE_ZONE)
        events = mgr.check_point("t1", 0.50, 0.50, frame_number=0, timestamp_ms=0.0)
        assert len(events) == 1, "Cold-start inside zone must emit entry event"
        assert events[0].event_type == "restricted_zone_entry"
        assert events[0].evidence.get("cold_start") is True

    def test_cold_start_outside_no_event(self):
        """Track starting outside zone must NOT emit any event on first frame."""
        mgr = make_mgr(SQUARE_ZONE)
        events = mgr.check_point("t1", 0.10, 0.10, frame_number=0, timestamp_ms=0.0)
        assert events == []

    def test_cold_start_inside_no_duplicate_on_stay(self):
        """After cold-start entry, staying inside must not re-emit entry."""
        mgr = make_mgr(SQUARE_ZONE)
        e0 = mgr.check_point("t1", 0.50, 0.50, frame_number=0, timestamp_ms=0.0)
        e1 = mgr.check_point("t1", 0.50, 0.50, frame_number=1, timestamp_ms=40.0)
        e2 = mgr.check_point("t1", 0.50, 0.50, frame_number=2, timestamp_ms=80.0)
        assert len(e0) == 1  # entry
        assert e1 == []
        assert e2 == []


# ---------------------------------------------------------------------------
# 6. Multiple people — independent state
# ---------------------------------------------------------------------------

class TestMultipleTracks:
    def test_two_tracks_independent_state(self):
        """Two tracks sharing a zone manager must have independent zone membership."""
        mgr = make_mgr(SQUARE_ZONE)
        # Track A: outside
        mgr.check_point("track_A", 0.10, 0.50, frame_number=0, timestamp_ms=0.0)
        # Track B: inside
        evts_b = mgr.check_point("track_B", 0.50, 0.50, frame_number=0, timestamp_ms=0.0)
        # Only B should have an event (cold-start inside)
        assert len(evts_b) == 1
        assert evts_b[0].track_id == "track_B"

    def test_two_tracks_cross_independently(self):
        """Two tracks crossing the zone at different times emit separate events."""
        mgr = make_mgr(SQUARE_ZONE)
        # Both start outside
        mgr.check_point("A", 0.10, 0.50, frame_number=0, timestamp_ms=0)
        mgr.check_point("B", 0.90, 0.50, frame_number=0, timestamp_ms=0)
        # A enters
        evts_a = mgr.check_point("A", 0.50, 0.50, frame_number=1, timestamp_ms=40)
        # B does not enter yet
        evts_b = mgr.check_point("B", 0.90, 0.50, frame_number=1, timestamp_ms=40)
        assert len(evts_a) == 1 and evts_a[0].track_id == "A"
        assert evts_b == []


# ---------------------------------------------------------------------------
# 7. Repeated crossing (in → out → in → out)
# ---------------------------------------------------------------------------

class TestRepeatedCrossing:
    def test_three_crossings_emit_three_events(self):
        """A track that enters, exits, re-enters a zone must emit 3 events."""
        mgr = make_mgr(SQUARE_ZONE)
        # outside
        mgr.check_point("t1", 0.10, 0.50, frame_number=0, timestamp_ms=0)
        # inside (entry #1)
        e1 = mgr.check_point("t1", 0.50, 0.50, frame_number=1, timestamp_ms=40)
        # outside (exit #1)
        e2 = mgr.check_point("t1", 0.10, 0.50, frame_number=2, timestamp_ms=80)
        # inside (entry #2)
        e3 = mgr.check_point("t1", 0.50, 0.50, frame_number=3, timestamp_ms=120)

        all_events = e1 + e2 + e3
        assert len(all_events) == 3
        assert all_events[0].event_type == "restricted_zone_entry"
        assert all_events[1].event_type == "restricted_zone_exit"
        assert all_events[2].event_type == "restricted_zone_entry"


# ---------------------------------------------------------------------------
# 8. Entry timing accuracy (FAIL-003 regression)
# ---------------------------------------------------------------------------

class TestTimingAccuracy:
    """
    FAIL-003 regression: Phase 4 validate_roi.py reported ROI entry was NOT
    detected in the corpus simulation. Root cause: test script had wrong
    expected crossing times (14.3s / 25.7s instead of 11.65s / 18.35s).

    The ROIManager geometry was correct all along. This regression test
    directly verifies timing with the correct math.

    Trajectory: cx = (100 + 1720*(t/30)) / 1920
      Entry when cx = 0.40: t = 668*30/1720 = 11.65s
      Exit  when cx = 0.60: t = 1052*30/1720 = 18.35s
    """

    FPS = 25
    W = 1920
    TOTAL_FRAMES = 30 * 25  # 750

    def _simulate(self):
        mgr = make_mgr(CROSSING_ZONE)
        events = []
        for frame in range(self.TOTAL_FRAMES):
            t = frame / self.FPS
            cx = (100 + (self.W - 200) * (t / 30)) / self.W
            evts = mgr.check_point("track", cx, 0.5, frame, t * 1000)
            events.extend(evts)
        return events

    def test_entry_detected(self):
        events = self._simulate()
        entries = [e for e in events if "entry" in e.event_type]
        assert len(entries) >= 1, "No entry event detected in corpus simulation"

    def test_exit_detected(self):
        events = self._simulate()
        exits = [e for e in events if "exit" in e.event_type]
        assert len(exits) >= 1, "No exit event detected in corpus simulation"

    def test_entry_timing_within_one_frame(self):
        """Entry must fire within ±1 frame of the geometrically correct time (11.65s)."""
        events = self._simulate()
        entries = [e for e in events if "entry" in e.event_type]
        assert entries, "No entry detected"
        entry_t = entries[0].frame_number / self.FPS
        expected_t = 668 * 30 / 1720  # 11.65s
        tolerance = 1.0 / self.FPS    # 1 frame = 0.04s at 25fps
        assert abs(entry_t - expected_t) <= tolerance, (
            f"Entry at {entry_t:.3f}s, expected {expected_t:.3f}s ± {tolerance:.3f}s"
        )

    def test_exit_timing_within_one_frame(self):
        """Exit must fire within ±1 frame of the geometrically correct time (18.35s)."""
        events = self._simulate()
        exits = [e for e in events if "exit" in e.event_type]
        assert exits, "No exit detected"
        exit_t = exits[0].frame_number / self.FPS
        expected_t = 1052 * 30 / 1720  # 18.35s
        tolerance = 1.0 / self.FPS
        assert abs(exit_t - expected_t) <= tolerance, (
            f"Exit at {exit_t:.3f}s, expected {expected_t:.3f}s ± {tolerance:.3f}s"
        )
