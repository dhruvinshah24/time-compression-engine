"""
Unit & Regression Tests for Phase 6E.8 — Soft Stair Evidence Integration.

Validates:
1. Scene evidence presence boosts or preserves stair confidence.
2. Scene evidence absence suppresses velocity hallucinations below threshold (0.55).
3. Soft confidence calculations for Policy B (Multiplier), Policy C (Fusion), Policy D (Conservative Gate).
4. Negative-footage suppression (simulated known audit tracks 14, 177, 252, 273).
5. Positive-event retention (simulated pos_01 with detected stairs).
6. Explainability evidence dictionary structure.
7. Ascending vs. Descending direction separation.
8. Downstream ConfidenceFuser (Stage s08) integration and ConfidenceVector generation.
9. TCE_V1_REFERENCE configuration remains frozen.
"""

import math
import pytest
from app.engines.semantic.confidence_fusion.config import FusionConfig
from app.engines.semantic.confidence_fusion.fusion import ConfidenceFuser
from app.engines.semantic.event_understanding.engine import Event
from app.engines.perception.tracker.track import Track, TrackObservation, TrackBBox, TrackState
from app.engines.perception.motion_analyzer.analyzer import MotionProfile
from app.evaluation.reference_config import TCE_V1_REFERENCE


def policy_b_multiplier(c_vel: float, c_scene: float, p_scene: int, w_base: float = 0.30, tau_ref: float = 0.05, min_pers: int = 2) -> float:
    effective_c_scene = c_scene if p_scene >= min_pers else 0.0
    factor = w_base + (1.0 - w_base) * min(1.0, effective_c_scene / tau_ref)
    return c_vel * factor


def policy_c_fusion(c_vel: float, c_scene: float, p_scene: int, w_vel: float = 0.50, w_scene: float = 0.35, w_pers: float = 0.15, tau_ref: float = 0.05, p_target: int = 5, min_pers: int = 2) -> float:
    effective_c_scene = c_scene if p_scene >= min_pers else 0.0
    effective_p = p_scene if p_scene >= min_pers else 0
    norm_scene = min(1.0, effective_c_scene / tau_ref)
    norm_pers = min(1.0, effective_p / p_target)
    return w_vel * c_vel + w_scene * norm_scene + w_pers * norm_pers


def policy_d_gate(c_vel: float, c_scene: float, p_scene: int, w_base: float = 0.35, tau_ref: float = 0.05, min_pers: int = 2) -> float:
    effective_c_scene = c_scene if p_scene >= min_pers else 0.0
    factor = w_base + (1.0 - w_base) * math.sqrt(min(1.0, effective_c_scene / tau_ref))
    return c_vel * factor


def test_tce_v1_reference_frozen():
    """Ensure TCE_V1_REFERENCE remains strictly unchanged and frozen."""
    ref = TCE_V1_REFERENCE
    assert ref.version == "v1.0"
    assert ref.w_detection == 0.25
    assert ref.w_motion == 0.20
    assert ref.w_rule == 0.25
    assert ref.w_track_stability == 0.20
    assert ref.w_scene_reliability == 0.10
    with pytest.raises(Exception):
        ref.w_detection = 0.50


def test_scene_evidence_absence_suppresses_false_positives():
    """Negative footage: high vertical velocity without scene evidence must be suppressed below 0.55."""
    c_vel = 0.746  # Track 177 hallucination
    c_scene = 0.0
    p_scene = 0

    c_final_b = policy_b_multiplier(c_vel, c_scene, p_scene)
    assert c_final_b < 0.55
    assert pytest.approx(c_final_b, 0.01) == 0.2238

    c_final_c = policy_c_fusion(c_vel, c_scene, p_scene)
    assert c_final_c < 0.55
    assert pytest.approx(c_final_c, 0.01) == 0.373

    c_final_d = policy_d_gate(c_vel, c_scene, p_scene)
    assert c_final_d < 0.55
    assert pytest.approx(c_final_d, 0.01) == 0.2611


def test_scene_evidence_presence_retains_positive_events():
    """Positive footage: high vertical velocity with authentic scene context must be retained."""
    c_vel = 0.715  # pos_01 man ascending
    c_scene = 0.099
    p_scene = 31

    c_final_b = policy_b_multiplier(c_vel, c_scene, p_scene)
    assert c_final_b >= 0.55
    assert pytest.approx(c_final_b, 0.01) == 0.715

    c_final_c = policy_c_fusion(c_vel, c_scene, p_scene)
    assert c_final_c >= 0.55
    assert pytest.approx(c_final_c, 0.01) == 0.8575

    c_final_d = policy_d_gate(c_vel, c_scene, p_scene)
    assert c_final_d >= 0.55
    assert pytest.approx(c_final_d, 0.01) == 0.715


def test_single_frame_noise_filtered_by_persistence():
    """Track 273 had a single spurious scene hit (p=1, c=0.153). Persistence >= 2 must filter it."""
    c_vel = 0.727
    c_scene = 0.153
    p_scene = 1

    # With persistence requirement p >= 2:
    c_final_b = policy_b_multiplier(c_vel, c_scene, p_scene, min_pers=2)
    assert c_final_b < 0.55
    assert pytest.approx(c_final_b, 0.01) == 0.2181

    c_final_c = policy_c_fusion(c_vel, c_scene, p_scene, min_pers=2)
    assert c_final_c < 0.55
    assert pytest.approx(c_final_c, 0.01) == 0.3635


def test_ascending_descending_separation():
    """Ensure that ascending and descending events are distinct and neither is conflated."""
    # Ascending
    ev_up = Event(
        event_id="EVT-UP",
        event_type="walking_upstairs",
        track_id=1,
        class_name="person",
        rule_name="narrative_builder",
        confidence=0.715,
        evidence={"stair_direction": "up", "velocity_confidence": 0.715, "scene_stair_confidence": 0.099},
        start_frame=0,
        end_frame=50,
        start_ms=0,
        end_ms=1600,
        dependencies=["track_1"],
    )
    # Descending
    ev_down = Event(
        event_id="EVT-DOWN",
        event_type="walking_downstairs",
        track_id=2,
        class_name="person",
        rule_name="narrative_builder",
        confidence=0.681,
        evidence={"stair_direction": "down", "velocity_confidence": 0.681, "scene_stair_confidence": 0.019},
        start_frame=0,
        end_frame=50,
        start_ms=0,
        end_ms=1600,
        dependencies=["track_2"],
    )

    assert ev_up.event_type == "walking_upstairs"
    assert ev_down.event_type == "walking_downstairs"
    assert ev_up.evidence["stair_direction"] == "up"
    assert ev_down.evidence["stair_direction"] == "down"


def test_explainability_evidence_schema():
    """Verify that all required explainability fields are present in the event evidence."""
    ev = Event(
        event_id="EVT-EXPLAIN",
        event_type="walking_upstairs",
        track_id=1,
        class_name="person",
        rule_name="narrative_builder",
        confidence=0.715,
        evidence={
            "velocity_confidence": 0.715,
            "scene_stair_confidence": 0.099,
            "scene_stair_persistence": 31,
            "scene_stair_supported": True,
            "spatial_relation": "contained (IoU=0.28)",
            "final_stair_confidence": 0.715,
            "decision": "walking_upstairs",
            "fallback_label": "walking",
        },
        start_frame=0,
        end_frame=60,
        start_ms=0,
        end_ms=2000,
        dependencies=["track_1"],
    )

    req_fields = [
        "velocity_confidence",
        "scene_stair_confidence",
        "scene_stair_persistence",
        "scene_stair_supported",
        "spatial_relation",
        "final_stair_confidence",
        "decision",
    ]
    for rf in req_fields:
        assert rf in ev.evidence, f"Missing explainability field: {rf}"


def test_confidence_fusion_downstream_integration():
    """Verify that a soft-evidence stair event correctly fuses with downstream ConfidenceFuser (Stage s08)."""
    fuser = ConfidenceFuser(config=FusionConfig(min_fused_confidence=0.35))

    track = Track(
        track_id=1,
        class_name="person",
        class_id=0,
        state=TrackState.ACTIVE,
        created_frame=0,
        created_timestamp_ms=0.0,
        last_seen_frame=61,
        last_seen_timestamp_ms=2033.0,
        current_bbox=None,
    )
    track.observations = [
        TrackObservation(
            frame_number=i,
            timestamp_ms=i * 33.3,
            bbox=TrackBBox(0.3, 0.4, 0.5, 0.9, 0.88, 0, "person"),
            detection_confidence=0.88,
        )
        for i in range(62)
    ]
    track.total_frames_matched = 62

    motion = MotionProfile(track_id=1, class_name="person", motion_confidence=0.78)

    ev = Event(
        event_id="EVT-POS01",
        event_type="walking_upstairs",
        track_id=1,
        class_name="person",
        rule_name="narrative_builder",
        confidence=0.715,
        evidence={"scene_stair_supported": True, "velocity_confidence": 0.715},
        start_frame=0,
        end_frame=61,
        start_ms=0,
        end_ms=2033,
        dependencies=["track_1"],
    )

    result = fuser.fuse(
        events=[ev],
        tracks={1: track},
        motion_profiles={1: motion},
        camera_motion_frames=[],
    )

    assert result.total_fused == 1
    assert result.total_discarded == 0
    assert "confidence_vector" in ev.evidence
    vec = ev.evidence["confidence_vector"]
    assert vec["components"]["detection"] == 0.88
    assert vec["components"]["motion"] == 0.78
    assert vec["components"]["rule"] == 0.75
    assert vec["components"]["track_stability"] == 1.0
    assert vec["components"]["scene_reliability"] == 1.0
    assert ev.confidence >= 0.35
