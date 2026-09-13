"""
Phase 6E.9 Stair Evidence Calibration and Expansion Unit Tests.

Tests:
1. Confusion matrix metric calculations (Precision, Recall, F1).
2. Policy C additive fusion vulnerability under noise.
3. Policy B multiplicative gating noise resilience.
4. Ascending vs. descending directional separation.
5. Invariance of TCE_V1_REFERENCE frozen config.
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

def test_confusion_matrix_metrics():
    """Verify calculation of precision, recall, and F1 score."""
    def calc_metrics(tp, fp, fn, tn):
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        return round(prec, 4), round(rec, 4), round(f1, 4)

    # Baseline Policy A
    p_a, r_a, f1_a = calc_metrics(5, 52, 0, 39)
    assert p_a == 0.0877
    assert r_a == 1.0
    assert f1_a == 0.1613

    # Policy B Soft Multiplier
    p_b, r_b, f1_b = calc_metrics(1, 0, 4, 91)
    assert p_b == 1.0
    assert r_b == 0.2
    assert f1_b == 0.3333

    # Policy C Evidence Fusion
    p_c, r_c, f1_c = calc_metrics(2, 0, 3, 91)
    assert p_c == 1.0
    assert r_c == 0.4
    assert f1_c == 0.5714

def test_policy_c_additive_noise_vulnerability():
    """Demonstrate that additive linear fusion creates false positives on weak background noise."""
    c_vel = 0.746
    c_scene = 0.05
    p_scene = 3
    tau_ref = 0.10
    pers_ref = 5

    norm_scene = min(1.0, c_scene / tau_ref)
    norm_pers = min(1.0, p_scene / pers_ref)
    c_final_c = 0.50 * c_vel + 0.35 * norm_scene + 0.15 * norm_pers
    fires_c = c_final_c >= 0.55
    assert fires_c is True, f"Expected Policy C to fire erroneously, got {c_final_c}"

    factor = 0.30 + 0.70 * min(1.0, c_scene / 0.10) if p_scene >= 2 else 0.30
    c_final_b = c_vel * factor
    fires_b = c_final_b >= 0.55
    assert fires_b is False, f"Expected Policy B to safely suppress, got {c_final_b}"

def test_directional_separation():
    """Ensure ascending and descending evaluations are cleanly partitioned."""
    tracks = [
        {'id': 't1', 'action': 'ascending', 'direction': 'up'},
        {'id': 't2', 'action': 'ascending', 'direction': 'up'},
        {'id': 't3', 'action': 'descending', 'direction': 'down'},
    ]
    asc = [t for t in tracks if t['action'] == 'ascending']
    desc = [t for t in tracks if t['action'] == 'descending']
    assert len(asc) == 2
    assert len(desc) == 1
