"""
TCE Reference Configuration — v1.0

Per mentor recommendations:
  "Freeze a reference configuration before tuning."
  "Add git_commit to every benchmark result. That creates complete
   reproducibility: code version, configuration, dataset, results."

This module defines an immutable snapshot of every pipeline parameter that
affects output quality. It is the configuration used for all Phase 11
benchmark runs. Any deviation — even a small threshold change — should be
treated as a new configuration variant (v1.1, v2.0, etc.) and benchmarked
separately.

Reproducibility chain (embedded in every benchmark result JSON):
  git_commit     — exact code version (auto-detected from git)
  version        — configuration version label ("v1.0")
  to_dict()      — all 15 pipeline parameters
  → Together these uniquely identify the experiment.

Usage in benchmark_runner.py:
    from app.evaluation.reference_config import TCE_V1_REFERENCE
    settings = TCE_V1_REFERENCE.to_pipeline_settings()
    context = PipelineContext(..., settings=settings)
    result["config"] = TCE_V1_REFERENCE.to_dict()  # embed commit + params

Usage in evaluation reports:
    result["config"] = TCE_V1_REFERENCE.to_dict()
    # Every result file now carries its own reproducibility proof.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any


def _detect_git_commit() -> str:
    """
    Return the short git commit hash of the current HEAD.

    Falls back gracefully if:
      - git is not installed
      - the project is not in a git repository
      - any subprocess error occurs

    The fallback is "unknown" — never raises.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        commit = result.stdout.strip()
        return commit if commit else "unknown"
    except Exception:
        return "unknown"


@dataclass(frozen=True)
class ReferenceConfig:
    """
    Immutable, versioned snapshot of all pipeline parameters.

    frozen=True: any attempt to modify a field after construction raises
    FrozenInstanceError. This is intentional — the reference config must
    not be mutated during benchmarking.

    Reproducibility fields:
      version     — configuration label ("v1.0", "v1.1-geometric", ...)
      git_commit  — short git commit hash of the code that produced results
                    Auto-detected at construction; falls back to "unknown".
                    Embed in every benchmark result via to_dict().

    Parameter groups (see field comments below for details).
    """

    # Reproducibility
    version: str = "v1.0"
    git_commit: str = field(default_factory=_detect_git_commit)

    # Video ingestion
    # frame_skip: process every N-th frame (5 = 6 fps from a 30 fps source)
    frame_skip: int = 5

    # Object detection
    detection_threshold: float = 0.72

    # Motion analysis
    motion_threshold: float = 0.015   # normalized displacement per frame

    # Confidence fusion
    fusion_strategy: str = "weighted_linear"
    w_detection: float = 0.25
    w_motion: float = 0.20
    w_rule: float = 0.25
    w_track_stability: float = 0.20
    w_scene_reliability: float = 0.10

    # Story preservation
    story_gap_threshold_ms: float = 5000.0

    # Ranking
    rank_w_importance: float = 0.40
    rank_w_narrative: float = 0.60

    # Compression policy
    compression_target_ratio: float = 0.40
    compression_keep_complete: bool = True
    compression_chain_atomicity: bool = True
    compression_min_threshold: float = 0.20

    def __post_init__(self) -> None:
        # Validate fusion weights sum to 1.0
        total = (
            self.w_detection + self.w_motion + self.w_rule
            + self.w_track_stability + self.w_scene_reliability
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Fusion weights must sum to 1.0, got {total:.4f}"
            )

        # Validate rank weights sum to 1.0
        rank_total = self.rank_w_importance + self.rank_w_narrative
        if abs(rank_total - 1.0) > 0.01:
            raise ValueError(
                f"Rank weights must sum to 1.0, got {rank_total:.4f}"
            )

        # Validate ratios in valid range
        if not (0.0 < self.compression_target_ratio <= 1.0):
            raise ValueError(
                f"compression_target_ratio must be in (0, 1], "
                f"got {self.compression_target_ratio}"
            )

        if self.fusion_strategy not in (
            "weighted_linear", "geometric", "harmonic", "min"
        ):
            raise ValueError(
                f"Unknown fusion_strategy: {self.fusion_strategy}"
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize to a plain dict for embedding in benchmark result JSON.

        Every benchmark result should include this dict. The result format
        matches the mentor's recommended structure exactly:

            {
              "reference_config": "TCE v1.0",
              "git_commit": "a1b2c3d",
              "benchmark": "...",
              "metrics": { ... }
            }

        Months later you will still know which code version and which
        configuration produced a given result.
        """
        return {
            "version": self.version,
            "git_commit": self.git_commit,
            "frame_skip": self.frame_skip,
            "detection_threshold": self.detection_threshold,
            "motion_threshold": self.motion_threshold,
            "fusion": {
                "strategy": self.fusion_strategy,
                "weights": {
                    "detection": self.w_detection,
                    "motion": self.w_motion,
                    "rule": self.w_rule,
                    "track_stability": self.w_track_stability,
                    "scene_reliability": self.w_scene_reliability,
                },
            },
            "story": {
                "gap_threshold_ms": self.story_gap_threshold_ms,
            },
            "ranking": {
                "w_importance": self.rank_w_importance,
                "w_narrative": self.rank_w_narrative,
            },
            "compression": {
                "target_ratio": self.compression_target_ratio,
                "keep_complete": self.compression_keep_complete,
                "chain_atomicity": self.compression_chain_atomicity,
                "min_threshold": self.compression_min_threshold,
            },
        }

    def to_pipeline_settings(self) -> dict[str, Any]:
        """
        Convert to the flat dict format consumed by PipelineContext.settings.

        Keys match what s10_rank.py, s11_summarize.py, etc. read from context.
        """
        return {
            "frame_skip": self.frame_skip,
            "detection_threshold": self.detection_threshold,
            "motion_threshold": self.motion_threshold,
            "fusion_strategy": self.fusion_strategy,
            "fusion_w_detection": self.w_detection,
            "fusion_w_motion": self.w_motion,
            "fusion_w_rule": self.w_rule,
            "fusion_w_track_stability": self.w_track_stability,
            "fusion_w_scene_reliability": self.w_scene_reliability,
            "story_gap_threshold_ms": self.story_gap_threshold_ms,
            "rank_w_importance": self.rank_w_importance,
            "rank_w_narrative": self.rank_w_narrative,
            "compression_target_ratio": self.compression_target_ratio,
            "compression_keep_complete": self.compression_keep_complete,
            "compression_chain_atomicity": self.compression_chain_atomicity,
            "compression_min_threshold": self.compression_min_threshold,
        }

    def variant(self, **overrides: Any) -> "ReferenceConfig":
        """
        Create a new config variant by overriding specific fields.

        Use this for ablation studies — never mutate TCE_V1_REFERENCE directly.

        Example:
            v1_geometric = TCE_V1_REFERENCE.variant(
                version="v1.1-geometric",
                fusion_strategy="geometric",
            )
        """
        current = self.to_dict()
        # Flatten the nested dict for dataclass field mapping
        fields = {
            "version": current["version"],
            "git_commit": current["git_commit"],
            "frame_skip": current["frame_skip"],
            "detection_threshold": current["detection_threshold"],
            "motion_threshold": current["motion_threshold"],
            "fusion_strategy": current["fusion"]["strategy"],
            "w_detection": current["fusion"]["weights"]["detection"],
            "w_motion": current["fusion"]["weights"]["motion"],
            "w_rule": current["fusion"]["weights"]["rule"],
            "w_track_stability": current["fusion"]["weights"]["track_stability"],
            "w_scene_reliability": current["fusion"]["weights"]["scene_reliability"],
            "story_gap_threshold_ms": current["story"]["gap_threshold_ms"],
            "rank_w_importance": current["ranking"]["w_importance"],
            "rank_w_narrative": current["ranking"]["w_narrative"],
            "compression_target_ratio": current["compression"]["target_ratio"],
            "compression_keep_complete": current["compression"]["keep_complete"],
            "compression_chain_atomicity": current["compression"]["chain_atomicity"],
            "compression_min_threshold": current["compression"]["min_threshold"],
        }
        fields.update(overrides)
        return ReferenceConfig(**fields)


# ---------------------------------------------------------------------------
# The canonical reference — import this in benchmark_runner.py
# ---------------------------------------------------------------------------

TCE_V1_REFERENCE = ReferenceConfig()
