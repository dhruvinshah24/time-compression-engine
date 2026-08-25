"""
Unit tests for roi_manager.py — TCE Accuracy Overhaul v1.0.1.

Tests verify:
  - point_in_polygon: inside/outside/edge cases
  - Zone loading: valid config, insufficient vertices, bad zone_type
  - check_point: no event on first observation, event on crossing
  - No duplicate events when track stays inside
  - Multiple zones: independent event per zone
  - Zone membership tracking reset via reset_track()
  - Empty zones config → no events
  - centroid_from_bbox helper

No GPU required. No real video files required.
"""

import pytest

from app.utils.roi_manager import (
    ROIManager,
    ROIZone,
    ZoneEvent,
    ZoneType,
)


# ── Point-in-polygon tests ─────────────────────────────────────────────────

class TestPointInPolygon:
    """Test the ray-casting point-in-polygon algorithm."""

    # Simple square: (0,0)-(1,0)-(1,1)-(0,1)
    SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

    def test_center_is_inside(self):
        assert ROIManager._point_in_polygon(0.5, 0.5, self.SQUARE) is True

    def test_outside_right(self):
        assert ROIManager._point_in_polygon(1.5, 0.5, self.SQUARE) is False

    def test_outside_left(self):
        assert ROIManager._point_in_polygon(-0.1, 0.5, self.SQUARE) is False

    def test_outside_top(self):
        assert ROIManager._point_in_polygon(0.5, -0.1, self.SQUARE) is False

    def test_outside_bottom(self):
        assert ROIManager._point_in_polygon(0.5, 1.5, self.SQUARE) is False

    def test_corner_near_inside(self):
        # Near corner but clearly inside
        assert ROIManager._point_in_polygon(0.01, 0.01, self.SQUARE) is True

    def test_far_outside(self):
        assert ROIManager._point_in_polygon(10.0, 10.0, self.SQUARE) is False

    def test_triangle(self):
        # Triangle: (0,0), (1,0), (0.5, 1)
        tri = [(0.0, 0.0), (1.0, 0.0), (0.5, 1.0)]
        # Centroid is inside
        assert ROIManager._point_in_polygon(0.5, 0.4, tri) is True
        # Far outside
        assert ROIManager._point_in_polygon(0.0, 1.0, tri) is False

    def test_l_shaped_zone(self):
        # L-shaped zone
        l_shape = [
            (0.0, 0.0), (0.5, 0.0), (0.5, 0.5),
            (1.0, 0.5), (1.0, 1.0), (0.0, 1.0)
        ]
        # Inside lower-left of L
        assert ROIManager._point_in_polygon(0.25, 0.75, l_shape) is True
        # Inside upper-right of L
        assert ROIManager._point_in_polygon(0.75, 0.75, l_shape) is True
        # Outside (the missing corner of L)
        assert ROIManager._point_in_polygon(0.75, 0.25, l_shape) is False


# ── Zone loading tests ─────────────────────────────────────────────────────

class TestLoadZones:

    def test_load_valid_config(self):
        mgr = ROIManager()
        mgr.load_zones([
            {
                "zone_id": "z1",
                "name": "Test Zone",
                "zone_type": "restricted",
                "polygon": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
            }
        ])
        assert len(mgr._zones) == 1
        assert mgr._zones[0].zone_id == "z1"
        assert mgr._zones[0].zone_type == ZoneType.RESTRICTED

    def test_skip_zone_with_too_few_points(self):
        mgr = ROIManager()
        mgr.load_zones([
            {
                "zone_id": "bad",
                "name": "Bad Zone",
                "zone_type": "restricted",
                "polygon": [[0.0, 0.0], [1.0, 1.0]],  # only 2 points
            }
        ])
        assert len(mgr._zones) == 0

    def test_empty_config_loads_zero_zones(self):
        mgr = ROIManager()
        mgr.load_zones([])
        assert len(mgr._zones) == 0

    def test_multiple_zones(self):
        mgr = ROIManager()
        mgr.load_zones([
            {
                "zone_id": "z1", "name": "A", "zone_type": "restricted",
                "polygon": [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]],
            },
            {
                "zone_id": "z2", "name": "B", "zone_type": "safe",
                "polygon": [[0.5, 0.5], [1, 0.5], [1, 1], [0.5, 1]],
            },
        ])
        assert len(mgr._zones) == 2

    def test_invalid_zone_type_skipped(self):
        mgr = ROIManager()
        mgr.load_zones([
            {
                "zone_id": "z1", "name": "Bad", "zone_type": "nonexistent_type",
                "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
            }
        ])
        # Should be skipped without crashing
        assert len(mgr._zones) == 0


# ── check_point tests ──────────────────────────────────────────────────────

class TestCheckPoint:

    SQUARE_ZONE_CFG = [
        {
            "zone_id": "z1",
            "name": "Test Restricted",
            "zone_type": "restricted",
            "polygon": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]],
        }
    ]

    def make_mgr(self) -> ROIManager:
        mgr = ROIManager()
        mgr.load_zones(self.SQUARE_ZONE_CFG)
        return mgr

    def test_first_observation_no_event(self):
        """First check_point call for a track → no event (just initializes state)."""
        mgr = self.make_mgr()
        events = mgr.check_point("track_1", 0.5, 0.5, frame_number=1, timestamp_ms=100.0)
        assert events == []

    def test_track_stays_inside_no_duplicate_event(self):
        """Track inside zone across 3 consecutive frames → only 0 events (no re-fire)."""
        mgr = self.make_mgr()
        # First observation (inside)
        mgr.check_point("track_1", 0.5, 0.5, frame_number=1, timestamp_ms=100.0)
        # Stay inside
        e1 = mgr.check_point("track_1", 0.5, 0.5, frame_number=2, timestamp_ms=200.0)
        e2 = mgr.check_point("track_1", 0.5, 0.5, frame_number=3, timestamp_ms=300.0)
        assert e1 == []
        assert e2 == []

    def test_outside_to_inside_fires_entry_event(self):
        """Track starts outside zone, moves inside → restricted_zone_entry event."""
        mgr = self.make_mgr()
        # First observation: outside
        mgr.check_point("track_1", 0.05, 0.05, frame_number=1, timestamp_ms=100.0)
        # Move inside
        events = mgr.check_point("track_1", 0.5, 0.5, frame_number=2, timestamp_ms=200.0)
        assert len(events) == 1
        assert events[0].event_type == "restricted_zone_entry"
        assert events[0].direction == "entering"
        assert events[0].zone_id == "z1"
        assert events[0].track_id == "track_1"
        assert events[0].frame_number == 2

    def test_inside_to_outside_fires_exit_event(self):
        """Track starts inside zone, moves outside → restricted_zone_exit event."""
        mgr = self.make_mgr()
        # First observation: inside
        mgr.check_point("track_1", 0.5, 0.5, frame_number=1, timestamp_ms=100.0)
        # Move outside
        events = mgr.check_point("track_1", 0.05, 0.05, frame_number=2, timestamp_ms=200.0)
        assert len(events) == 1
        assert events[0].event_type == "restricted_zone_exit"
        assert events[0].direction == "exiting"

    def test_re_entry_fires_new_event(self):
        """Track exits and re-enters zone → two events total."""
        mgr = self.make_mgr()
        mgr.check_point("track_1", 0.5, 0.5, frame_number=1, timestamp_ms=100.0)  # inside
        mgr.check_point("track_1", 0.05, 0.05, frame_number=2, timestamp_ms=200.0)  # exit
        events_re_entry = mgr.check_point("track_1", 0.5, 0.5, frame_number=3, timestamp_ms=300.0)
        assert len(events_re_entry) == 1
        assert events_re_entry[0].event_type == "restricted_zone_entry"

    def test_empty_zones_no_events(self):
        """With no zones loaded, check_point returns empty list."""
        mgr = ROIManager()
        events = mgr.check_point("track_1", 0.5, 0.5, frame_number=1, timestamp_ms=100.0)
        assert events == []

    def test_multiple_tracks_independent(self):
        """Two tracks have independent zone membership states."""
        mgr = self.make_mgr()
        # track_1: inside from first observation
        mgr.check_point("track_1", 0.5, 0.5, frame_number=1, timestamp_ms=100.0)
        # track_2: outside from first observation
        mgr.check_point("track_2", 0.05, 0.05, frame_number=1, timestamp_ms=100.0)

        # track_1 exits
        evts1 = mgr.check_point("track_1", 0.05, 0.05, frame_number=2, timestamp_ms=200.0)
        # track_2 enters
        evts2 = mgr.check_point("track_2", 0.5, 0.5, frame_number=2, timestamp_ms=200.0)

        assert len(evts1) == 1 and evts1[0].event_type == "restricted_zone_exit"
        assert len(evts2) == 1 and evts2[0].event_type == "restricted_zone_entry"

    def test_event_contains_evidence_dict(self):
        """ZoneEvent.evidence should be a non-empty dict."""
        mgr = self.make_mgr()
        mgr.check_point("track_1", 0.05, 0.05, frame_number=1, timestamp_ms=100.0)
        events = mgr.check_point("track_1", 0.5, 0.5, frame_number=2, timestamp_ms=200.0)
        assert events
        assert isinstance(events[0].evidence, dict)
        assert "zone_id" in events[0].evidence
        assert "direction" in events[0].evidence


# ── reset_track tests ──────────────────────────────────────────────────────

class TestResetTrack:

    def test_reset_clears_membership(self):
        """After reset_track, the track's state is gone."""
        mgr = ROIManager()
        mgr.load_zones([
            {
                "zone_id": "z1", "name": "Zone", "zone_type": "restricted",
                "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
            }
        ])
        mgr.check_point("track_1", 0.5, 0.5, frame_number=1, timestamp_ms=100.0)
        assert "track_1" in mgr._membership
        mgr.reset_track("track_1")
        assert "track_1" not in mgr._membership

    def test_reset_unknown_track_no_error(self):
        """Resetting an unknown track raises no error."""
        mgr = ROIManager()
        mgr.reset_track("nonexistent")  # Should not raise


# ── centroid_from_bbox helper ─────────────────────────────────────────────

class TestCentroidFromBbox:

    def test_center_of_frame(self):
        cx, cy = ROIManager.centroid_from_bbox([0.0, 0.0, 1.0, 1.0])
        assert abs(cx - 0.5) < 1e-9
        assert abs(cy - 0.5) < 1e-9

    def test_top_left_bbox(self):
        cx, cy = ROIManager.centroid_from_bbox([0.0, 0.0, 0.2, 0.2])
        assert abs(cx - 0.1) < 1e-9
        assert abs(cy - 0.1) < 1e-9

    def test_small_bbox(self):
        cx, cy = ROIManager.centroid_from_bbox([0.4, 0.4, 0.6, 0.6])
        assert abs(cx - 0.5) < 1e-9
        assert abs(cy - 0.5) < 1e-9
