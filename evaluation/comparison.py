"""
Utilities for comparing evaluation metrics across different TCE variants.
"""

from .metrics import EvaluationResult
from typing import Dict

def compare_variants(baseline: EvaluationResult, experimental: EvaluationResult) -> Dict[str, float]:
    """
    Compares two EvaluationResult objects to determine relative performance.
    Useful for A/B testing story preservation on vs off.
    """
    return {
        "f1_delta": experimental.f1_score - baseline.f1_score,
        "narrative_delta": experimental.narrative_preservation_score - baseline.narrative_preservation_score,
        "compression_delta": experimental.compression_ratio - baseline.compression_ratio,
        "speed_delta_fps": experimental.processing_speed_fps - baseline.processing_speed_fps
    }

def print_comparison(baseline_name: str, baseline: EvaluationResult, 
                     experimental_name: str, experimental: EvaluationResult):
    print(f"--- Baseline ({baseline_name}) ---")
    print(baseline.summary())
    print(f"\n--- Experimental ({experimental_name}) ---")
    print(experimental.summary())
    print("\n--- Deltas ---")
    deltas = compare_variants(baseline, experimental)
    for k, v in deltas.items():
        print(f"{k}: {v:+.4f}")
