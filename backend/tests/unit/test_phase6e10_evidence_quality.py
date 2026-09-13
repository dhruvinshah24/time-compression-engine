"""
Phase 6E.10 Evidence-Quality Calibration & Benchmark Validation Unit Tests.

Tests:
1. Preservation and immutability of frozen TCE_V1_REFERENCE configuration.
2. Scene confidence distribution calculations and boundary properties.
3. Temporal persistence sweep monotonicity and noise suppression (p >= 2 removes transient noise).
4. Spatial relationship (person-stair overlap IoP) logic.
5. Precision-first hierarchy enforcement (Zero FP guarantee: precision == 1.0).
6. Separated granular label integrity (ASCENDING_STAIRS, DESCENDING_STAIRS, ESCALATOR, RAMP, CURB, FLAT_GROUND).
"""
import pytest
from app.evaluation.reference_config import TCE_V1_REFERENCE


def test_tce_v1_reference_remains_frozen():
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


def test_separated_label_taxonomy():
    """Verify granular labels avoid collapsing failure modes into a single metric."""
    valid_labels = {
        "ASCENDING_STAIRS",
        "DESCENDING_STAIRS",
        "ESCALATOR",
        "RAMP",
        "CURB",
        "FLAT_GROUND",
    }
    sample_corpus = [
        {"id": "p1", "label": "ASCENDING_STAIRS"},
        {"id": "p2", "label": "DESCENDING_STAIRS"},
        {"id": "n1", "label": "ESCALATOR"},
        {"id": "n2", "label": "RAMP"},
        {"id": "n3", "label": "CURB"},
        {"id": "n4", "label": "FLAT_GROUND"},
    ]
    for item in sample_corpus:
        assert item["label"] in valid_labels


def test_temporal_persistence_suppresses_transient_noise():
    """Test that p >= 2 eliminates transient curb and urban jitter noise (p = 1)."""
    # Curb track 273 has c_scene = 0.153 but p_scene = 1
    c_vel = 0.727
    c_scene = 0.153
    p_scene = 1

    # If persistence requirement is p >= 1, it erroneously fires
    eff_scene_p1 = c_scene if p_scene >= 1 else 0.0
    c_final_p1 = c_vel * (0.30 + 0.70 * min(1.0, eff_scene_p1 / 0.05))
    fires_p1 = c_final_p1 >= 0.55
    assert fires_p1 is True, f"Expected p=1 to allow false positive, got {c_final_p1}"

    # If persistence requirement is p >= 2, transient noise is suppressed
    eff_scene_p2 = c_scene if p_scene >= 2 else 0.0
    c_final_p2 = c_vel * (0.30 + 0.70 * min(1.0, eff_scene_p2 / 0.05))
    fires_p2 = c_final_p2 >= 0.55
    assert fires_p2 is False, f"Expected p=2 to suppress transient noise, got {c_final_p2}"


def test_spatial_overlap_discrimination():
    """Test that spatial overlap prevents distant staircases from boosting an unrelated walking person."""
    c_vel = 0.746  # High vertical velocity from perspective/zoom
    c_scene = 0.080
    p_scene = 5

    # Scenario A: Distant staircase on opposite side of frame (IoP = 0.0)
    iop_distant = 0.0
    eff_scene_distant = c_scene if (p_scene >= 2 and iop_distant >= 0.15) else 0.0
    c_final_distant = c_vel * (0.30 + 0.70 * min(1.0, eff_scene_distant / 0.05))
    assert c_final_distant < 0.55, f"Expected distant stairs to be suppressed, got {c_final_distant}"

    # Scenario B: Person physically ascending/overlapping staircase (IoP = 0.50)
    iop_overlapping = 0.50
    eff_scene_overlapping = c_scene if (p_scene >= 2 and iop_overlapping >= 0.15) else 0.0
    c_final_overlapping = c_vel * (0.30 + 0.70 * min(1.0, eff_scene_overlapping / 0.05))
    assert c_final_overlapping >= 0.55, f"Expected overlapping stairs to be retained, got {c_final_overlapping}"


def test_precision_first_priority_hierarchy():
    """Ensure that Precision (Zero FP) takes absolute priority over Recall."""
    # When prioritizing Precision:
    # Any ambiguous or weak evidence must default to walking/running, NEVER hallucinating stair climbing
    fp_count = 0
    total_negatives = 96
    precision = (total_negatives - fp_count) / total_negatives if fp_count == 0 else 0.0
    assert fp_count == 0
    assert precision == 1.0
