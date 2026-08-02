"""
Confidence Fusion configuration — Phase 7.

The five signal dimensions and their default weights are defined here.
Per mentor guidance, treat weights as configurable parameters, not constants.
Different datasets (parking lot, hospital corridor, outdoor street)
may benefit from different weightings.

Weight validation:
  Weights must sum to 1.0. The config validates this on construction.
  If running benchmark experiments, adjust weights via system_settings
  and track the effect on precision/recall in reports/phase-07-report.md.

Fusion strategy:
  Default: weighted linear combination.
  Configurable: can be swapped to geometric mean, harmonic mean, or
  min-component via fusion_strategy field.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FusionConfig:
    """
    Weights for the 5-dimensional confidence fusion.

    Dimension    Default    Rationale
    -----------  -------    ---------
    detection    0.30       The detector's raw confidence is the primary signal.
    motion       0.25       Motion quality strongly predicts event reliability.
    rule         0.20       Rule specificity is a meaningful prior.
    track_stab   0.15       Long, continuous tracks are more credible.
    scene_rel    0.10       Camera motion and scene quality affect reliability.

    fusion_strategy: "weighted_linear" | "geometric" | "harmonic" | "min"
    """
    w_detection: float = 0.30
    w_motion: float = 0.25
    w_rule: float = 0.20
    w_track_stability: float = 0.15
    w_scene_reliability: float = 0.10

    fusion_strategy: str = "weighted_linear"

    # Gate: discard fused events below this threshold
    min_fused_confidence: float = 0.35

    # Track stability normalization: "fully stable" at this many matched frames
    full_stability_frames: int = 10

    # Scene reliability: fraction of event frames in camera-motion = fully unreliable
    camera_motion_full_penalty_fraction: float = 0.7

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        total = (
            self.w_detection + self.w_motion + self.w_rule
            + self.w_track_stability + self.w_scene_reliability
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"FusionConfig weights must sum to 1.0, got {total:.4f}. "
                f"Adjust w_detection/w_motion/w_rule/w_track_stability/w_scene_reliability."
            )
