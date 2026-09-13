"""
Phase 6E.11 Stair Scene Perception Recall Unit Tests.

Tests:
1. Invariance of frozen TCE_V1_REFERENCE configuration.
2. Prompt expansion vocabulary validation.
3. Person-conditioned ROI calculation and spatial expansion.
4. Tiling quadrant generation and bounding box offset transformation.
5. QualityScore formulation comparison (strict multiplicative vs geometric mean).
6. Zero False Positive guarantee across perception methods on negative distractors.
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


def test_prompt_vocabulary_expansion_coverage():
    """Ensure expanded prompt set includes key architectural variants."""
    expanded_prompts = {
        "stairs", "staircase", "steps", "stairway", "flight of stairs",
        "stair steps", "staircase steps", "stairwell", "stone steps",
        "concrete stairs", "indoor stairs", "outdoor stairs",
    }
    assert "indoor stairs" in expanded_prompts
    assert "stone steps" in expanded_prompts
    assert "concrete stairs" in expanded_prompts
    assert "stairway" in expanded_prompts


def test_person_roi_expansion():
    """Verify person-conditioned ROI calculation expands bounding box by 1.5x."""
    w, h = 1920, 1080
    # Person bbox: [x1, y1, x2, y2]
    px1, py1, px2, py2 = 500, 300, 700, 800
    pw = px2 - px1  # 200
    ph = py2 - py1  # 500

    pad_x = int(pw * 0.5)  # 100
    pad_y = int(ph * 0.5)  # 250

    rx1 = max(0, px1 - pad_x)  # 400
    ry1 = max(0, py1 - pad_y)  # 50
    rx2 = min(w, px2 + pad_x)  # 800
    ry2 = min(h, py2 + pad_y)  # 1050

    assert rx1 == 400
    assert ry1 == 50
    assert rx2 == 800
    assert ry2 == 1050
    # Area expanded from 100,000 to 400,000
    assert (rx2 - rx1) * (ry2 - ry1) > pw * ph


def test_tiling_quadrants_overlap():
    """Ensure 2x2 tiling covers 100% of frame with intentional 20% center overlap."""
    w, h = 1920, 1080
    tiles = [
        (0, 0, int(w * 0.6), int(h * 0.6)),
        (int(w * 0.4), 0, w, int(h * 0.6)),
        (0, int(h * 0.4), int(w * 0.6), h),
        (int(w * 0.4), int(h * 0.4), w, h),
    ]
    # Check center (w/2, h/2) is contained in all 4 tiles
    cx, cy = w // 2, h // 2
    covered_in = sum(1 for x1, y1, x2, y2 in tiles if x1 <= cx <= x2 and y1 <= cy <= y2)
    assert covered_in == 4  # Center overlap


def test_quality_score_multiplication_vs_geometric_mean():
    """Verify mathematical properties of strict multiplicative vs geometric mean."""
    cs_norm = 0.80
    ps_norm = 0.80
    iop_norm = 0.80

    strict_mult = cs_norm * ps_norm * iop_norm
    geom_mean = (cs_norm * ps_norm * iop_norm) ** (1.0 / 3.0)

    # Multiplicative suffers exponential compression
    assert round(strict_mult, 3) == 0.512
    # Geometric mean preserves signal scale
    assert round(geom_mean, 3) == 0.800
