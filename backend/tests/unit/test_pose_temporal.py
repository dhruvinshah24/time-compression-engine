"""
Tests: Temporal Pose Analyzer (Phase 3).

Tests validate the TemporalPoseAnalyzer state machine using synthetic
pose sequences. Key principle: single frames must NOT trigger activity
events. Multiple consecutive frames are required.

Status: IMPLEMENTED — unit tested with synthetic pose sequences.
        NOT YET VALIDATED on real footage with labelled activities.
"""

import pytest
from app.utils.pose_temporal import (
    TemporalPoseAnalyzer,
    SimplePoseFrame,
    STATE_STANDING,
    STATE_CROUCHING,
    STATE_CRAWLING,
    STATE_RUNNING,
    STATE_FALLEN,
    STATE_WALKING,
    STATE_UNKNOWN,
    _BODY_HEIGHT_CROUCHING_MAX,
    _BODY_HEIGHT_CRAWLING_MAX,
    _BODY_HEIGHT_FALLEN_MAX,
    _ASPECT_RATIO_HORIZONTAL,
    _HORIZONTAL_DISP_RUNNING,
    _HORIZONTAL_DISP_CRAWLING,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _standing_frame(frame_num: int, track_id: int = 1, cx: float = 0.5) -> SimplePoseFrame:
    """Typical standing person: tall bbox, normal aspect ratio."""
    return SimplePoseFrame(
        frame_number=frame_num,
        timestamp_ms=float(frame_num * 40),
        track_id=track_id,
        bbox_x=cx - 0.04,
        bbox_y=0.2,
        bbox_w=0.08,
        bbox_h=0.30,      # 30% frame height → standing
        body_height_ratio=0.30,
        bbox_aspect_ratio=0.08 / 0.30,   # ~0.27 narrow
        centroid_x=cx,
        centroid_y=0.35,
        pose_confidence=0.85,
    )


def _crouching_frame(frame_num: int, track_id: int = 1, cx: float = 0.5) -> SimplePoseFrame:
    """Crouching person: compressed bbox height, small lateral movement."""
    return SimplePoseFrame(
        frame_number=frame_num,
        timestamp_ms=float(frame_num * 40),
        track_id=track_id,
        bbox_x=cx - 0.06,
        bbox_y=0.6,
        bbox_w=0.12,
        bbox_h=0.15,      # 15% frame height → crouching range
        body_height_ratio=0.15,
        bbox_aspect_ratio=0.12 / 0.15,   # ~0.8
        centroid_x=cx,
        centroid_y=0.67,
        pose_confidence=0.75,
    )


def _crawling_frame(frame_num: int, track_id: int = 1, cx: float = None) -> SimplePoseFrame:
    """Crawling person: very low body height + lateral movement."""
    if cx is None:
        cx = 0.3 + frame_num * 0.008  # slowly moving right
    return SimplePoseFrame(
        frame_number=frame_num,
        timestamp_ms=float(frame_num * 40),
        track_id=track_id,
        bbox_x=cx - 0.08,
        bbox_y=0.75,
        bbox_w=0.16,
        bbox_h=0.10,      # 10% frame height → crawling range
        body_height_ratio=0.10,
        bbox_aspect_ratio=0.16 / 0.10,   # 1.6 — somewhat wide but not horizontal
        centroid_x=cx,
        centroid_y=0.80,
        pose_confidence=0.70,
    )


def _running_frame(frame_num: int, track_id: int = 1) -> SimplePoseFrame:
    """Running person: fast lateral movement."""
    cx = 0.1 + frame_num * 0.025  # fast movement right
    return SimplePoseFrame(
        frame_number=frame_num,
        timestamp_ms=float(frame_num * 40),
        track_id=track_id,
        bbox_x=cx - 0.04,
        bbox_y=0.3,
        bbox_w=0.08,
        bbox_h=0.28,
        body_height_ratio=0.28,
        bbox_aspect_ratio=0.08 / 0.28,
        centroid_x=cx,
        centroid_y=0.44,
        pose_confidence=0.80,
    )


def _fallen_frame(frame_num: int, track_id: int = 1) -> SimplePoseFrame:
    """Fallen person: horizontal wide bbox, very low body height."""
    return SimplePoseFrame(
        frame_number=frame_num,
        timestamp_ms=float(frame_num * 40),
        track_id=track_id,
        bbox_x=0.3,
        bbox_y=0.85,
        bbox_w=0.35,      # very wide
        bbox_h=0.08,      # very short
        body_height_ratio=0.08,
        bbox_aspect_ratio=0.35 / 0.08,   # 4.375 → very horizontal
        centroid_x=0.475,
        centroid_y=0.89,
        pose_confidence=0.60,
    )


# ── Tests: single frame does NOT generate event ───────────────────────────────

def test_single_crouch_frame_no_event():
    """One crouching frame must not generate an event."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crouching=3, hysteresis_frames=2)
    event = analyzer.update(_crouching_frame(0))
    assert event is None


def test_single_running_frame_no_event():
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_running=4, hysteresis_frames=2)
    event = analyzer.update(_running_frame(0))
    assert event is None


def test_single_fallen_frame_no_event():
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_fallen=2, hysteresis_frames=2)
    event = analyzer.update(_fallen_frame(0))
    assert event is None


# ── Tests: sustained crouching generates event ────────────────────────────────

def test_sustained_crouching_generates_event():
    """5 consecutive crouching frames → person_crouching_sustained event."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crouching=3, hysteresis_frames=2)
    events = []
    for i in range(6):
        e = analyzer.update(_crouching_frame(i))
        if e:
            events.append(e)
    # Also check flush
    events.extend(analyzer.flush())

    # At least one crouching event should be generated
    crouching = [e for e in events if "crouch" in e.event_type]
    assert len(crouching) >= 1, f"Expected crouching event, got: {[e.event_type for e in events]}"


def test_crouching_event_has_required_fields():
    analyzer = TemporalPoseAnalyzer(track_id=2, min_frames_crouching=3, hysteresis_frames=2)
    events = []
    for i in range(8):
        e = analyzer.update(_crouching_frame(i, track_id=2))
        if e:
            events.append(e)
    events.extend(analyzer.flush())

    crouching = [e for e in events if "crouch" in e.event_type]
    if crouching:
        ev = crouching[0]
        assert ev.track_id == 2
        assert ev.start_frame >= 0
        assert ev.end_frame >= ev.start_frame
        assert 0.0 < ev.confidence <= 1.0
        assert isinstance(ev.supporting_frames, list)
        assert len(ev.supporting_frames) > 0
        assert "reason" in ev.to_pipeline_event_dict()["evidence"]


# ── Tests: crawling detection requires full sequence ─────────────────────────

def test_crawling_requires_multiple_frames():
    """Single crawling frame should not trigger event."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crawling=5, hysteresis_frames=2)
    # One crawling frame preceded by standing
    for i in range(5):
        analyzer.update(_standing_frame(i))
    event = analyzer.update(_crawling_frame(5))
    assert event is None or "crawl" not in event.event_type


def test_sustained_crawling_generates_event():
    """5+ consecutive crawling frames → person_crawling event."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crawling=4, hysteresis_frames=2)
    events = []
    for i in range(10):
        e = analyzer.update(_crawling_frame(i))
        if e:
            events.append(e)
    events.extend(analyzer.flush())

    crawling = [e for e in events if "crawl" in e.event_type]
    assert len(crawling) >= 1, f"Expected crawling event; got {[e.event_type for e in events]}"


def test_crawling_event_contains_state_sequence():
    """Crawling event evidence must contain state_sequence field."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crawling=4, hysteresis_frames=2)
    events = []
    for i in range(3):
        analyzer.update(_standing_frame(i))
    for i in range(3, 12):
        e = analyzer.update(_crawling_frame(i))
        if e:
            events.append(e)
    events.extend(analyzer.flush())

    crawling = [e for e in events if "crawl" in e.event_type]
    if crawling:
        evidence = crawling[0].to_pipeline_event_dict()["evidence"]
        assert "state_sequence" in evidence


# ── Tests: hysteresis prevents noise flip ────────────────────────────────────

def test_hysteresis_prevents_single_noisy_frame():
    """Standing × 10, one crouching frame, standing × 5 → no crouching event."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crouching=3, hysteresis_frames=3)
    events = []
    for i in range(10):
        e = analyzer.update(_standing_frame(i))
        if e:
            events.append(e)
    # Single crouching frame (noise)
    e = analyzer.update(_crouching_frame(10))
    if e:
        events.append(e)
    for i in range(11, 16):
        e = analyzer.update(_standing_frame(i))
        if e:
            events.append(e)
    events.extend(analyzer.flush())

    crouching = [e for e in events if "crouch" in e.event_type]
    assert len(crouching) == 0, f"Hysteresis should suppress single noisy frame, but got: {crouching}"


# ── Tests: running detection ──────────────────────────────────────────────────

def test_running_requires_multiple_frames():
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_running=4, hysteresis_frames=2)
    # Only 2 running frames
    events = []
    for i in range(2):
        e = analyzer.update(_running_frame(i))
        if e:
            events.append(e)

    running = [e for e in events if "running" in e.event_type]
    assert len(running) == 0


# ── Tests: fallen detection ───────────────────────────────────────────────────

def test_fallen_detected_from_horizontal_bbox():
    """Horizontal wide bbox after walking → person_falling_likely."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_fallen=2, hysteresis_frames=2)
    events = []
    # Some walking first
    for i in range(5):
        e = analyzer.update(_standing_frame(i))
        if e:
            events.append(e)
    # Then fallen
    for i in range(5, 10):
        e = analyzer.update(_fallen_frame(i))
        if e:
            events.append(e)
    events.extend(analyzer.flush())

    fallen = [e for e in events if "fall" in e.event_type]
    assert len(fallen) >= 1, f"Expected fallen event; got {[e.event_type for e in events]}"


# ── Tests: flush returns pending events ──────────────────────────────────────

def test_flush_returns_pending_events():
    """Crouching frames at end of video — flush() must return the event."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crouching=3, hysteresis_frames=2)
    # Feed standing then crouching but never return to standing
    for i in range(3):
        analyzer.update(_standing_frame(i))
    for i in range(3, 9):
        analyzer.update(_crouching_frame(i))

    flushed = analyzer.flush()
    crouching = [e for e in flushed if "crouch" in e.event_type]
    assert len(crouching) >= 1, "flush() should return pending crouching event"


# ── Tests: pipeline dict format ───────────────────────────────────────────────

def test_pose_event_to_pipeline_dict_format():
    """PoseEvent.to_pipeline_event_dict() returns pipeline-compatible dict."""
    analyzer = TemporalPoseAnalyzer(track_id=1, min_frames_crouching=3, hysteresis_frames=2)
    events = []
    for i in range(8):
        e = analyzer.update(_crouching_frame(i))
        if e:
            events.append(e)
    events.extend(analyzer.flush())

    if events:
        d = events[0].to_pipeline_event_dict()
        assert "event_type" in d
        assert "track_id" in d
        assert "confidence" in d
        assert "evidence" in d
        assert "rule_name" in d
        assert d["rule_name"] == "temporal_pose_analysis"
