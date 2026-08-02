"""
Evaluation metrics for Time Compression Engine.

This module defines research-grade evaluation metrics that go beyond
standard computer vision benchmarks to assess narrative preservation
and human-perceived quality of compressed videos.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any

@dataclass
class EvaluationResult:
    # Standard metrics
    compression_ratio: float          # input_duration / output_duration
    temporal_precision: float         # relevant_included / total_included
    temporal_recall: float            # relevant_included / total_relevant
    f1_score: float                   # harmonic mean of precision & recall
    
    # Coverage metrics  
    event_coverage: float             # % of ground truth events captured
    false_positive_rate: float        # % of included events that are irrelevant
    
    # Research-grade metrics
    narrative_preservation_score: float  # Story coherence vs ground truth
    human_satisfaction_score: Optional[float] = None  # Subjective quality
    
    # Performance metrics
    processing_speed_fps: float = 0.0
    storage_saved_pct: float = 0.0
    total_processing_seconds: float = 0.0
    
    @property
    def is_valid(self) -> bool:
        return 0 <= self.temporal_precision <= 1 and 0 <= self.temporal_recall <= 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "compression_ratio": self.compression_ratio,
            "temporal_precision": self.temporal_precision,
            "temporal_recall": self.temporal_recall,
            "f1_score": self.f1_score,
            "event_coverage": self.event_coverage,
            "false_positive_rate": self.false_positive_rate,
            "narrative_preservation_score": self.narrative_preservation_score,
            "human_satisfaction_score": self.human_satisfaction_score,
            "processing_speed_fps": self.processing_speed_fps,
            "storage_saved_pct": self.storage_saved_pct,
            "total_processing_seconds": self.total_processing_seconds
        }
    
    def summary(self) -> str:
        return (
            f"Compression: {self.compression_ratio:.1f}:1 | "
            f"Precision: {self.temporal_precision:.2%} | "
            f"Recall: {self.temporal_recall:.2%} | "
            f"F1: {self.f1_score:.2%} | "
            f"Narrative: {self.narrative_preservation_score:.2%}"
        )
