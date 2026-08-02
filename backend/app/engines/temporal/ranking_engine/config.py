"""Configuration for Phase 9: Ranking Engine.

Per mentor guidance: importance and narrative value are independent dimensions.
Their weights in the combined rank are configurable so you can measure the
effect of different weightings on the evaluation corpus.

Research question this enables:
  "Does weighting narrative value higher than importance produce better
   summaries as judged by human evaluators?"
  → Run benchmark with (w_narrative=0.4, w_importance=0.6) vs reversed.
"""
from dataclasses import dataclass


@dataclass
class RankingConfig:
    """
    Weights for combining the two independent score dimensions.

    w_importance + w_narrative must sum to 1.0.

    Default: narrative value weighted higher (0.60) than importance (0.40).
    Rationale: a system that preserves narrative coherence is more valuable
    than one that only keeps "exciting" events without context.
    """
    w_importance: float = 0.40
    w_narrative: float = 0.60

    # Motion intensity normalization ceiling: events faster than this are
    # considered "fully intense" (motion_intensity = 1.0)
    max_motion_intensity: float = 0.05   # normalized units/sec (empirical)

    def __post_init__(self) -> None:
        total = self.w_importance + self.w_narrative
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"RankingConfig weights must sum to 1.0, got {total:.4f}"
            )
