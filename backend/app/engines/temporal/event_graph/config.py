"""Configuration for Phase 8: Event Graph."""
from dataclasses import dataclass


@dataclass
class EventGraphConfig:
    """
    Configuration for the Event Graph builder.

    max_co_occurrence_gap_ms:
        Maximum time gap between two events to create a CO_OCCURRENCE edge.

    same_track_edge_weight:
        Weight assigned to SAME_TRACK_TEMPORAL edges (strong causal link).

    co_occurrence_weight:
        Weight assigned to CO_OCCURRENCE edges (weaker — just time proximity).
    """
    max_co_occurrence_gap_ms: float = 2000.0
    same_track_edge_weight: float = 1.0
    co_occurrence_weight: float = 0.5
