"""Configuration for Phase 6: Semantic Event Understanding."""
from dataclasses import dataclass


@dataclass
class EventUnderstandingConfig:
    """
    Configuration for the rule-based event understanding engine.

    min_event_confidence:
        Events below this confidence are discarded before being stored.
        Raise to reduce noise. Lower to capture more marginal events.

    min_track_frames_for_entry:
        Minimum matched frames before a track is considered a valid entry event.
        Prevents very short ghost tracks from generating entry events.

    suppress_camera_motion_events:
        If True, tracks whose frames are entirely within camera-motion-dominated
        frames are excluded from event generation. This prevents camera pan/tilt
        from producing spurious events.
    """
    min_event_confidence: float = 0.4
    min_track_frames_for_entry: int = 2
    suppress_camera_motion_events: bool = True
