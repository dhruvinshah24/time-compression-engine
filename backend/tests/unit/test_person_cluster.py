"""
Unit tests for app.utils.person_cluster.
"""

from pathlib import Path
import numpy as np
import pytest

from app.utils.person_cluster import cluster_tracks_into_persons


def test_cluster_tracks_empty_clips():
    t_map, gallery = cluster_tracks_into_persons([])
    assert t_map == {}
    assert gallery == {}


def test_cluster_tracks_temporal_collision_prevention():
    """
    Two tracks that overlap in time by > 1.2s MUST NOT be merged,
    even if their appearances are similar.
    """
    clips = [
        # Track 1 active from 0 to 10s
        {"event_id": "e1", "track_id": 1, "start_ms": 0, "end_ms": 10000, "event_type": "walking"},
        # Track 2 active from 2s to 8s (complete temporal collision with Track 1)
        {"event_id": "e2", "track_id": 2, "start_ms": 2000, "end_ms": 8000, "event_type": "person_sitting"},
    ]

    t_map, gallery = cluster_tracks_into_persons(clips=clips, crops_dir=None, temporal_collision_ms=1000.0)

    # Must be separate persons because they were in the frame simultaneously!
    assert len(gallery) == 2
    assert t_map[1] != t_map[2]
    assert "Person 1" in gallery
    assert "Person 2" in gallery


def test_cluster_tracks_sequential_fragmentation_merging():
    """
    Fragmented tracks from the same person that do NOT collide in time
    and have close temporal proximity should be clustered.
    """
    clips = [
        # First fragment of person walking
        {"event_id": "e1", "track_id": 10, "start_ms": 0, "end_ms": 5000, "event_type": "walking"},
        # Lost track for 1.5s, then re-detected as track 20
        {"event_id": "e2", "track_id": 20, "start_ms": 6500, "end_ms": 12000, "event_type": "walking"},
        # Another person in the room concurrently
        {"event_id": "e3", "track_id": 99, "start_ms": 1000, "end_ms": 10000, "event_type": "person_sitting"},
    ]

    t_map, gallery = cluster_tracks_into_persons(clips=clips, crops_dir=None)

    # Track 10 and 20 should merge into one person (no collision, continuous sequence)
    # Track 99 collided with both, so it must be a separate person!
    assert t_map[10] == t_map[20]
    assert t_map[99] != t_map[10]
    assert len(gallery) == 2


def test_cluster_tracks_preserves_valid_gallery():
    """
    If raw_gallery is provided with complete track mappings, it is respected.
    """
    clips = [
        {"event_id": "e1", "track_id": 5, "start_ms": 0, "end_ms": 3000, "event_type": "walking"},
        {"event_id": "e2", "track_id": 8, "start_ms": 4000, "end_ms": 7000, "event_type": "walking"},
    ]
    raw_gallery = {
        "Person 1": {
            "person_label": "Person 1",
            "track_ids": [5, 8],
            "description": "Custom tracked subject",
            "first_seen_ms": 0,
            "last_seen_ms": 7000,
        }
    }

    t_map, gallery = cluster_tracks_into_persons(clips=clips, raw_gallery=raw_gallery)
    assert t_map[5] == "Person 1"
    assert t_map[8] == "Person 1"
    assert len(gallery) == 1
