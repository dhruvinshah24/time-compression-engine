"""
Track — the fundamental unit of multi-object tracking.

A Track represents the lifecycle of a single identified object
through the video. Every track gets a globally unique ID that persists
from the moment the object is first seen until it disappears.

Track lifecycle state machine:
    TENTATIVE  → Created, not yet confirmed (may be a false positive).
    ACTIVE     → Confirmed — matched for enough consecutive frames.
    LOST       → No match found this frame, still being searched.
    ENDED      → Exceeded max_lost_frames, permanently closed.

Why tentative vs active?
    Without a confirmation step, every single detection (including false
    positives from noise) creates a track. The tentative state requires
    a track to be matched for `min_confirmation_frames` before it is
    considered a real object. This dramatically reduces ghost tracks
    in low-quality or low-light footage.

Research note:
    The Track ID is globally unique within a job. This is important for
    the Event Graph in Phase 8 — two events connected by the same Track ID
    are definitionally about the same physical object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TrackState(str, Enum):
    """Track lifecycle states."""
    TENTATIVE = "tentative"   # Created, awaiting confirmation
    ACTIVE = "active"         # Confirmed object, being tracked
    LOST = "lost"             # Temporarily unmatched, searching
    ENDED = "ended"           # Permanently closed


@dataclass
class TrackBBox:
    """Bounding box associated with a track at a specific frame."""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int
    class_name: str

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass
class TrackObservation:
    """A single observation of a track at one frame."""
    frame_number: int
    timestamp_ms: float
    bbox: TrackBBox
    detection_confidence: float


@dataclass
class Track:
    """
    A single tracked object with its full history.

    track_id:             Globally unique identifier within a job.
    class_name:           Most common class name across observations.
    state:                Current lifecycle state.
    created_frame:        Frame where this track was first created.
    last_seen_frame:      Most recent frame where a match was found.
    observations:         Full history of matched detections.
    lost_frames:          Consecutive frames without a match.
    total_frames_active:  Frames in ACTIVE state (track quality metric).
    """
    track_id: int
    class_name: str
    class_id: int
    state: TrackState
    created_frame: int
    created_timestamp_ms: float
    last_seen_frame: int
    last_seen_timestamp_ms: float
    current_bbox: TrackBBox | None
    observations: list[TrackObservation] = field(default_factory=list)
    lost_frames: int = 0
    total_frames_matched: int = 0
    confirmed_at_frame: int | None = None

    @property
    def age_frames(self) -> int:
        """Total frames since this track was created."""
        return self.last_seen_frame - self.created_frame + 1

    @property
    def track_length_ms(self) -> float:
        """Duration from first to last observation in milliseconds."""
        return self.last_seen_timestamp_ms - self.created_timestamp_ms

    @property
    def avg_confidence(self) -> float:
        """Average detection confidence across all observations."""
        if not self.observations:
            return 0.0
        return sum(o.detection_confidence for o in self.observations) / len(self.observations)

    @property
    def is_confirmed(self) -> bool:
        return self.state in (TrackState.ACTIVE, TrackState.LOST)

    def update(
        self,
        frame_number: int,
        timestamp_ms: float,
        bbox: TrackBBox,
    ) -> None:
        """Update track with a new matched detection."""
        self.last_seen_frame = frame_number
        self.last_seen_timestamp_ms = timestamp_ms
        self.current_bbox = bbox
        self.lost_frames = 0
        self.total_frames_matched += 1
        self.observations.append(TrackObservation(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
            bbox=bbox,
            detection_confidence=bbox.confidence,
        ))

    def mark_lost(self) -> None:
        """Mark one frame without a match."""
        self.lost_frames += 1

    def end(self) -> None:
        """Permanently close this track."""
        self.state = TrackState.ENDED

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "class_id": self.class_id,
            "state": self.state.value,
            "created_frame": self.created_frame,
            "last_seen_frame": self.last_seen_frame,
            "age_frames": self.age_frames,
            "track_length_ms": self.track_length_ms,
            "total_frames_matched": self.total_frames_matched,
            "avg_confidence": round(self.avg_confidence, 4),
            "lost_frames": self.lost_frames,
            "observation_count": len(self.observations),
        }
