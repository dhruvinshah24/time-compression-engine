"""Configuration for the Multi-Object Tracker module."""
from dataclasses import dataclass


@dataclass
class TrackerConfig:
    """
    Configuration for Phase 4 Multi-Object Tracking.

    iou_threshold:
        Minimum IoU for a track-detection pair to be considered a valid match.
        Lower → more lenient matching (risk: wrong object matched).
        Higher → stricter matching (risk: real object loses its track ID).
        Default 0.3 is the standard SORT baseline.

    max_lost_frames:
        How many consecutive frames a track can go unmatched before it ends.
        Higher → more occlusion tolerance (risk: ghost tracks).
        Lower → faster track termination (risk: re-ID failure after occlusion).
        Default 3 is appropriate for 5fps extracted frames (~0.6s tolerance).

    min_confirmation_frames:
        Frames a track must be matched before moving from TENTATIVE → ACTIVE.
        Higher → fewer ghost tracks (risk: misses fast-moving objects).
        Lower → more responsive (risk: noise creates false tracks).
        Default 2 requires 2 consecutive matches.

    min_detection_confidence:
        Minimum detection confidence to create a new track.
        Prevents low-confidence noise from spawning tracks.
        Should be >= the detection stage's confidence_threshold.
    """
    iou_threshold: float = 0.3
    max_lost_frames: int = 3
    min_confirmation_frames: int = 2
    min_detection_confidence: float = 0.65
