"""
Phase 6E.13 Controlled Production Integration Unit & Regression Tests.

Validates:
1. Feature flag default=False preserves baseline behavior exactly.
2. Feature flag enable_scene_stair_guard=True activates stair scene evidence verification.
3. Automatic 1.5x person ROI calculation (no manual coordinates).
4. Full explainability evidence dict populated on verified and suppressed stair events.
5. Suppression of unverified stair events falls back to flat-ground activities (walking/running).
6. Non-stair activities (cycling, sitting, standing, loitering) are completely unaffected.
7. Verified stair events flow with enriched evidence into S08 confidence fusion.
8. Frozen configuration immutability: TCE_V1_REFERENCE remains strictly unchanged.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import MagicMock, patch

from app.engines.perception.tracker.track import Track, TrackBBox, TrackObservation, TrackState
from app.engines.semantic.event_understanding.engine import Event
from app.evaluation.reference_config import TCE_V1_REFERENCE
from app.pipeline.context import PipelineContext
from app.utils.activity_classifier import ActivityResult
from app.utils.scene_stair_guard import (
    SceneStairGuard,
    StairGuardEvidence,
    compute_iop,
    expand_person_roi,
    EXPANDED_STAIR_VOCABULARY,
    DEFAULT_STAIR_THRESH,
)


def test_tce_v1_reference_remains_frozen():
    """Requirement 1: TCE_V1_REFERENCE must remain strictly frozen."""
    ref = TCE_V1_REFERENCE
    assert ref.version == "v1.0"
    assert ref.w_detection == 0.25
    assert ref.w_motion == 0.20
    assert ref.w_rule == 0.25
    assert ref.w_track_stability == 0.20
    assert ref.w_scene_reliability == 0.10
    with pytest.raises(Exception):
        ref.w_detection = 0.50


def test_automatic_person_roi_expansion():
    """Requirement: Automatic 1.5x person ROI without manual coordinates."""
    frame_w, frame_h = 1920, 1080
    person_norm = [0.4, 0.3, 0.6, 0.8]  # pw = 0.2, ph = 0.5
    rx1, ry1, rx2, ry2 = expand_person_roi(person_norm, frame_w, frame_h, scale=1.5)

    assert rx1 < 0.4 * frame_w
    assert ry1 < 0.3 * frame_h
    assert rx2 > 0.6 * frame_w
    assert ry2 > 0.8 * frame_h
    assert (rx2 - rx1) > (0.6 - 0.4) * frame_w
    assert (ry2 - ry1) > (0.8 - 0.3) * frame_h


def test_compute_iop_formula():
    """Verify Intersection-over-Person (IoP) calculation."""
    person_norm = [0.2, 0.2, 0.4, 0.6]  # area = 0.2 * 0.4 = 0.08
    # 50% overlap of person
    stair_norm = [0.2, 0.2, 0.4, 0.4]   # inter = 0.2 * 0.2 = 0.04 -> iop = 0.5
    iop = compute_iop(person_norm, stair_norm)
    assert pytest.approx(iop, 0.001) == 0.50

    # No overlap
    stair_no_overlap = [0.5, 0.5, 0.8, 0.8]
    iop_zero = compute_iop(person_norm, stair_no_overlap)
    assert iop_zero == 0.0


def _build_dummy_track(track_id: int, obs_count: int = 10, is_stair: bool = True) -> Track:
    init_b = TrackBBox(
        x1=0.4, y1=0.5, x2=0.5, y2=0.65,
        confidence=0.85, class_id=0, class_name="person"
    )
    track = Track(
        track_id=track_id,
        class_id=0,
        class_name="person",
        state=TrackState.ACTIVE,
        created_frame=0,
        created_timestamp_ms=0.0,
        last_seen_frame=obs_count * 5,
        last_seen_timestamp_ms=obs_count * 167.0,
        current_bbox=init_b,
        confirmed_at_frame=1,
    )
    for i in range(obs_count):
        y_pos = 0.8 - (i * 0.04) if is_stair else 0.5
        b = TrackBBox(
            x1=0.4, y1=y_pos, x2=0.5, y2=y_pos + 0.15,
            confidence=0.85, class_id=0, class_name="person"
        )
        obs = TrackObservation(
            frame_number=i * 5,
            timestamp_ms=float(i * 167),
            bbox=b,
            detection_confidence=0.85,
        )
        track.observations.append(obs)
    return track


@pytest.mark.asyncio
async def test_feature_flag_false_preserves_baseline():
    """When enable_scene_stair_guard is False (default), raw stair activity passes through."""
    from app.pipeline.stages import s07_event_understand

    track = _build_dummy_track(track_id=14, is_stair=True)
    activity = ActivityResult(
        label="walking_upstairs",
        confidence=0.74,
        evidence={"stair_conf": 0.74, "stair_direction": "up", "mean_speed": 0.018},
    )

    ctx = PipelineContext(
        job_id="TEST-FLAG-FALSE",
        video_id="VID-1",
        video_path="dummy.mp4",
        output_dir="tmp/test",
        settings={"enable_scene_stair_guard": False},
        metadata={
            "all_tracks": [track],
            "track_activities": {14: activity},
            "track_to_label": {14: "Person 1"},
            "person_gallery": {},
        },
    )

    res = await s07_event_understand.run(ctx)
    assert res.success is True

    events = ctx.metadata.get("events", [])
    narrative_events = [e for e in events if e.rule_name == "narrative_builder"]
    assert len(narrative_events) == 1
    evt = narrative_events[0]
    assert evt.event_type == "walking_upstairs"
    assert evt.confidence == 0.74
    assert "stair_guard" not in evt.evidence


@pytest.mark.asyncio
async def test_feature_flag_true_suppresses_false_stair_with_explainability():
    """When enable_scene_stair_guard is True, unverified stair events are suppressed to walking."""
    from app.pipeline.stages import s07_event_understand

    track = _build_dummy_track(track_id=177, is_stair=True)
    activity = ActivityResult(
        label="walking_upstairs",
        confidence=0.75,
        evidence={"stair_conf": 0.75, "stair_direction": "up", "mean_speed": 0.016},
    )

    ctx = PipelineContext(
        job_id="TEST-FLAG-TRUE-SUPPRESS",
        video_id="VID-1",
        video_path="dummy.mp4",
        output_dir="tmp/test",
        settings={"enable_scene_stair_guard": True},
        metadata={
            "all_tracks": [track],
            "track_activities": {177: activity},
            "track_to_label": {177: "Person 2"},
            "person_gallery": {},
            "frame_paths": {0: "nonexistent_frame.jpg"},
        },
    )

    res = await s07_event_understand.run(ctx)
    assert res.success is True

    events = ctx.metadata.get("events", [])
    narrative_events = [e for e in events if e.rule_name == "narrative_builder"]
    assert len(narrative_events) == 1
    evt = narrative_events[0]

    # Guard suppressed the hallucination to walking
    assert evt.event_type == "walking"
    assert evt.evidence["stair_suppressed"] is True
    assert "stair_guard" in evt.evidence

    guard_ev = evt.evidence["stair_guard"]
    assert guard_ev["is_verified"] is False
    assert guard_ev["final_stair_confidence"] < DEFAULT_STAIR_THRESH
    assert guard_ev["fallback_activity_label"] == "walking"
    assert guard_ev["feature_flag_state"] is True


@pytest.mark.asyncio
async def test_non_stair_activities_unaffected_by_guard():
    """Activities like cycling, running, walking are not touched by the stair guard."""
    from app.pipeline.stages import s07_event_understand

    track_bike = _build_dummy_track(track_id=234, is_stair=False)
    activity_bike = ActivityResult(
        label="cycling",
        confidence=0.88,
        evidence={"mean_speed": 0.035},
    )

    ctx = PipelineContext(
        job_id="TEST-NON-STAIR",
        video_id="VID-1",
        video_path="dummy.mp4",
        output_dir="tmp/test",
        settings={"enable_scene_stair_guard": True},
        metadata={
            "all_tracks": [track_bike],
            "track_activities": {234: activity_bike},
            "track_to_label": {234: "Person 3"},
            "person_gallery": {},
        },
    )

    res = await s07_event_understand.run(ctx)
    assert res.success is True

    events = ctx.metadata.get("events", [])
    narrative_events = [e for e in events if e.rule_name == "narrative_builder"]
    assert len(narrative_events) == 1
    evt = narrative_events[0]
    assert evt.event_type == "cycling"
    assert evt.confidence == 0.88
    assert "stair_guard" not in evt.evidence


@pytest.mark.asyncio
async def test_stair_guard_verified_flows_to_s08_confidence_fusion():
    """Verified stair climbing events flow properly into Stage s08 Confidence Fusion."""
    from app.pipeline.stages import s07_event_understand, s08_confidence_fuse

    track = _build_dummy_track(track_id=1, is_stair=True)
    activity = ActivityResult(
        label="walking_upstairs",
        confidence=0.72,
        evidence={"stair_conf": 0.72, "stair_direction": "up", "mean_speed": 0.017},
    )

    ctx = PipelineContext(
        job_id="TEST-S08-FUSION",
        video_id="VID-1",
        video_path="dummy.mp4",
        output_dir="tmp/test",
        settings={"enable_scene_stair_guard": True},
        metadata={
            "all_tracks": [track],
            "track_activities": {1: activity},
            "track_to_label": {1: "Person 1"},
            "person_gallery": {},
        },
    )

    mock_guard_res = StairGuardEvidence(
        velocity_confidence=0.72,
        scene_stair_confidence=0.12,
        scene_stair_persistence=15,
        spatial_relation_iop=0.45,
        quality_score=1.0,
        final_stair_confidence=0.72,
        is_verified=True,
        decision_path="automatic_person_roi_scene_guard",
        feature_flag_state=True,
    )

    with patch("app.utils.scene_stair_guard.SceneStairGuard.evaluate_track_stair_context", return_value=mock_guard_res):
        res7 = await s07_event_understand.run(ctx)
        assert res7.success is True

        res8 = await s08_confidence_fuse.run(ctx)
        assert res8.success is True

        fused_events = ctx.metadata.get("fused_events", [])
        stair_events = [e for e in fused_events if e.event_type == "walking_upstairs"]
        assert len(stair_events) == 1
        stair_evt = stair_events[0]
        assert stair_evt.evidence["stair_verified"] is True
        assert "confidence_vector" in stair_evt.evidence
        assert stair_evt.confidence >= 0.35  # Passed fusion threshold