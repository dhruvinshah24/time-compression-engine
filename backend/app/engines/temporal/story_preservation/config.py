"""Configuration for Phase 8: Story Preservation."""
from dataclasses import dataclass


@dataclass
class StoryConfig:
    """
    Configuration for the Story Builder.

    narrative_score_weights:
        How much each factor contributes to the narrative importance score.
        Weights must sum to 1.0. Tune after benchmarking on the corpus.

    loitering_threshold_ms:
        How long a stationary person must be present before the segment is
        considered "high interest" for narrative purposes.

    co_occurrence_window_ms:
        Events from different tracks within this window are considered co-occurring
        (potentially interacting). Used to build CO_OCCURRENCE edges in the event graph.

    min_segment_confidence:
        Story segments below this mean confidence are marked as low-quality.
        They are retained but flagged, allowing compression policy to deprioritize them.
    """
    # Narrative score component weights (must sum to 1.0)
    weight_confidence: float = 0.40
    weight_completeness: float = 0.30
    weight_length: float = 0.20
    weight_duration: float = 0.10

    # Story completeness thresholds
    min_events_for_partial: int = 2
    full_length_events: int = 5        # segment with this many events = fully "long"
    full_duration_ms: float = 5000.0   # segment this long = fully "durable"

    # Interaction detection
    co_occurrence_window_ms: float = 2000.0   # 2 seconds

    # Quality gate
    min_segment_confidence: float = 0.35
