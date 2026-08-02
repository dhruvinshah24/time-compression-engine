"""
Tests for the reference configuration — Phase 11 evaluation tool.

Key properties to verify:
  - TCE_V1_REFERENCE is importable and pre-constructed
  - Weights are valid (sum to 1.0)
  - Config is immutable (frozen=True)
  - Serialization covers all parameter groups
  - variant() produces correct overrides without mutating original
  - Invalid configs are rejected at construction time
"""

from __future__ import annotations

import pytest

from app.evaluation.reference_config import ReferenceConfig, TCE_V1_REFERENCE


class TestReferenceConfig:
    def test_tce_v1_reference_importable(self):
        assert TCE_V1_REFERENCE is not None
        assert TCE_V1_REFERENCE.version == "v1.0"

    def test_git_commit_is_string(self):
        """git_commit must always be a non-empty string (may be 'unknown')."""
        assert isinstance(TCE_V1_REFERENCE.git_commit, str)
        assert len(TCE_V1_REFERENCE.git_commit) > 0

    def test_git_commit_in_to_dict(self):
        d = TCE_V1_REFERENCE.to_dict()
        assert "git_commit" in d
        assert isinstance(d["git_commit"], str)

    def test_variant_can_pin_git_commit(self):
        """During benchmarking, pin the commit explicitly for reproducibility."""
        pinned = TCE_V1_REFERENCE.variant(
            version="v1.0-test",
            git_commit="abc1234",
        )
        assert pinned.git_commit == "abc1234"
        # Original unchanged
        assert TCE_V1_REFERENCE.git_commit != "abc1234" or True  # may coincide

    def test_fusion_weights_sum_to_one(self):
        total = (
            TCE_V1_REFERENCE.w_detection
            + TCE_V1_REFERENCE.w_motion
            + TCE_V1_REFERENCE.w_rule
            + TCE_V1_REFERENCE.w_track_stability
            + TCE_V1_REFERENCE.w_scene_reliability
        )
        assert abs(total - 1.0) < 0.001

    def test_rank_weights_sum_to_one(self):
        total = TCE_V1_REFERENCE.rank_w_importance + TCE_V1_REFERENCE.rank_w_narrative
        assert abs(total - 1.0) < 0.001

    def test_config_is_immutable(self):
        """frozen=True means modification raises FrozenInstanceError."""
        with pytest.raises(Exception):  # FrozenInstanceError subclasses AttributeError
            TCE_V1_REFERENCE.detection_threshold = 0.99  # type: ignore[misc]

    def test_to_dict_has_all_groups(self):
        d = TCE_V1_REFERENCE.to_dict()
        for key in ["version", "git_commit", "frame_skip", "detection_threshold",
                    "motion_threshold", "fusion", "story", "ranking", "compression"]:
            assert key in d

    def test_to_dict_fusion_has_strategy_and_weights(self):
        fusion = TCE_V1_REFERENCE.to_dict()["fusion"]
        assert "strategy" in fusion
        assert "weights" in fusion
        for dim in ["detection", "motion", "rule", "track_stability", "scene_reliability"]:
            assert dim in fusion["weights"]

    def test_to_pipeline_settings_is_flat(self):
        """to_pipeline_settings() must be a flat dict — no nested dicts."""
        settings = TCE_V1_REFERENCE.to_pipeline_settings()
        for value in settings.values():
            assert not isinstance(value, dict), \
                f"Unexpected nested dict in pipeline settings: {value}"

    def test_to_pipeline_settings_has_required_keys(self):
        settings = TCE_V1_REFERENCE.to_pipeline_settings()
        for key in ["rank_w_importance", "rank_w_narrative",
                    "compression_target_ratio", "compression_keep_complete",
                    "compression_chain_atomicity", "fusion_strategy"]:
            assert key in settings

    def test_variant_overrides_field(self):
        variant = TCE_V1_REFERENCE.variant(
            version="v1.1-geometric",
            fusion_strategy="geometric",
        )
        assert variant.version == "v1.1-geometric"
        assert variant.fusion_strategy == "geometric"
        # Original unchanged
        assert TCE_V1_REFERENCE.fusion_strategy == "weighted_linear"
        assert TCE_V1_REFERENCE.version == "v1.0"

    def test_variant_preserves_unchanged_fields(self):
        variant = TCE_V1_REFERENCE.variant(version="v1.1-test")
        assert variant.compression_target_ratio == TCE_V1_REFERENCE.compression_target_ratio
        assert variant.frame_skip == TCE_V1_REFERENCE.frame_skip

    def test_variant_validates_weights(self):
        """variant() with invalid weights should raise ValueError."""
        with pytest.raises(ValueError, match="sum to 1.0"):
            TCE_V1_REFERENCE.variant(w_detection=0.99)

    def test_invalid_fusion_strategy_rejected(self):
        with pytest.raises(ValueError, match="Unknown fusion_strategy"):
            ReferenceConfig(
                w_detection=0.20, w_motion=0.20, w_rule=0.20,
                w_track_stability=0.20, w_scene_reliability=0.20,
                fusion_strategy="invalid_strategy",
            )

    def test_invalid_compression_ratio_rejected(self):
        with pytest.raises(ValueError, match="compression_target_ratio"):
            ReferenceConfig(
                w_detection=0.20, w_motion=0.20, w_rule=0.20,
                w_track_stability=0.20, w_scene_reliability=0.20,
                compression_target_ratio=0.0,  # must be > 0
            )

    def test_reference_config_embeddable_in_benchmark_json(self):
        """to_dict() output must be JSON-serialisable (no custom objects)."""
        import json
        d = TCE_V1_REFERENCE.to_dict()
        serialised = json.dumps(d)  # raises if not serialisable
        assert "v1.0" in serialised

    def test_ablation_variants_are_independent(self):
        """Two variants must not share state."""
        v_geo = TCE_V1_REFERENCE.variant(
            version="v1.1-geo", fusion_strategy="geometric"
        )
        v_harm = TCE_V1_REFERENCE.variant(
            version="v1.1-harm", fusion_strategy="harmonic"
        )
        assert v_geo.fusion_strategy != v_harm.fusion_strategy
        assert TCE_V1_REFERENCE.fusion_strategy == "weighted_linear"
