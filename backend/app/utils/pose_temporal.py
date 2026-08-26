"""
Temporal Pose / Body-Motion Analyzer — Time Compression Engine v1.0.1.

Single-frame pose classification (bbox aspect ratio or keypoint geometry)
cannot reliably detect sustained activities like crawling, crouching,
or falling. A person bent over to pick something up looks geometrically
identical to a person starting to crawl. Temporal evidence over multiple
consecutive frames resolves this ambiguity.

This module accumulates per-frame FramePose objects for a single tracked
person and applies a hysteresis-gated state machine to detect:

  STANDING  → normal upright posture
  WALKING   → upright + lateral displacement
  RUNNING   → upright + high lateral displacement
  LOWERING  → transitional: body height decreasing
  CROUCHING → compressed body height, limited lateral movement
  CRAWLING  → compressed + horizontal + lateral movement over time
  FALLEN    → sudden horizontal body orientation after movement
  SITTING   → stable compressed body height, minimal movement
  UNKNOWN   → insufficient data

Classification is based on MEASURABLE geometric features:
  - body_height_ratio:  bbox height / frame height (proxy for body size)
  - horizontal_disp:    lateral bbox centroid movement per frame
  - torso_angle:        estimated body tilt from vertical (keypoints or bbox)
  - bbox_aspect_ratio:  width / height (wider = more horizontal)

Hysteresis rule:
  A state transition is NOT accepted until hysteresis_frames consecutive
  frames agree on the new state. One noisy frame cannot flip the state.

Status:
  IMPLEMENTED — unit tested with synthetic sequences.
  NOT YET VALIDATED on real footage with labelled activities.
  Crawling specifically requires careful validation; geometric heuristics
  have known failure modes (e.g., person leaning over a desk).
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ── State constants ───────────────────────────────────────────────────────────
STATE_UNKNOWN    = "UNKNOWN"
STATE_STANDING   = "STANDING"
STATE_WALKING    = "WALKING"
STATE_RUNNING    = "RUNNING"
STATE_LOWERING   = "LOWERING"
STATE_CROUCHING  = "CROUCHING"
STATE_CRAWLING   = "CRAWLING"
STATE_FALLEN     = "FALLEN"
STATE_SITTING    = "SITTING"

ALL_STATES = [
    STATE_UNKNOWN, STATE_STANDING, STATE_WALKING, STATE_RUNNING,
    STATE_LOWERING, STATE_CROUCHING, STATE_CRAWLING, STATE_FALLEN, STATE_SITTING,
]

# ── Classification thresholds ─────────────────────────────────────────────────
# These are initial estimates. They should be calibrated against real footage.
# Until calibrated, all classification is: IMPLEMENTED, NOT YET VALIDATED.
_BODY_HEIGHT_STANDING_MIN   = 0.20   # person must occupy ≥20% frame height to be "standing"
_BODY_HEIGHT_CROUCHING_MAX  = 0.18   # bbox height < 18% frame height → likely crouching
_BODY_HEIGHT_CRAWLING_MAX   = 0.15   # bbox height < 15% frame height → possibly crawling
_BODY_HEIGHT_FALLEN_MAX     = 0.12   # very low → possibly fallen / sitting on floor
_ASPECT_RATIO_HORIZONTAL    = 1.8    # width/height > 1.8 → horizontal body orientation
_HORIZONTAL_DISP_WALKING    = 0.005  # >0.5% frame width per frame = walking speed
_HORIZONTAL_DISP_RUNNING    = 0.020  # >2% frame width per frame = running speed
_HORIZONTAL_DISP_CRAWLING   = 0.003  # >0.3% frame width per frame while crouched = crawling


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SimplePoseFrame:
    """
    Minimal pose features for one person in one frame.

    This is the input type for TemporalPoseAnalyzer. It can be populated from:
    - FramePose from pose_estimate.py (when pose model is active)
    - Bounding box geometry alone (fallback when pose model disabled)
    """
    frame_number:        int
    timestamp_ms:        float
    track_id:            int

    # Bounding box features (always available)
    bbox_x:              float   # normalized [0,1]
    bbox_y:              float   # normalized [0,1]
    bbox_w:              float   # normalized [0,1]
    bbox_h:              float   # normalized [0,1]

    # Derived features (computed from bbox + optional keypoints)
    body_height_ratio:   float   # bbox_h as fraction of frame height (approx = bbox_h for normalized)
    bbox_aspect_ratio:   float   # bbox_w / bbox_h
    centroid_x:          float   # horizontal center [0,1]
    centroid_y:          float   # vertical center [0,1]

    # Keypoint-derived (None if pose model not active or keypoints low confidence)
    torso_angle_deg:     Optional[float] = None  # 0=vertical, 90=horizontal
    pose_confidence:     float = 0.0

    @classmethod
    def from_bbox(
        cls,
        frame_number: int,
        timestamp_ms: float,
        track_id: int,
        x1: float, y1: float, x2: float, y2: float,
        frame_h: float = 1.0,
    ) -> "SimplePoseFrame":
        """Build from bounding box coordinates (normalized)."""
        w = x2 - x1
        h = y2 - y1
        return cls(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
            track_id=track_id,
            bbox_x=x1,
            bbox_y=y1,
            bbox_w=w,
            bbox_h=h,
            body_height_ratio=h / max(frame_h, 1.0),
            bbox_aspect_ratio=w / max(h, 0.001),
            centroid_x=x1 + w / 2,
            centroid_y=y1 + h / 2,
        )


@dataclass
class PoseEvent:
    """A temporally-confirmed activity event for one tracked person."""
    event_type:            str        # e.g. "person_crawling"
    track_id:              int
    start_frame:           int
    end_frame:             int
    start_ms:              float
    end_ms:                float
    confidence:            float      # overall confidence 0–1
    pose_confidence:       float      # average keypoint confidence
    temporal_confidence:   float      # fraction of frames in state agreeing
    supporting_frames:     list[int]  # frame numbers where state was confirmed
    state_sequence:        list[str]  # e.g. [STANDING, LOWERING, CROUCHING, CRAWLING]
    reason:                str        # human-readable explanation
    evidence:              dict = field(default_factory=dict)

    def to_pipeline_event_dict(self) -> dict:
        """Format for pipeline Event schema compatibility."""
        return {
            "event_type":    self.event_type,
            "track_id":      self.track_id,
            "start_frame":   self.start_frame,
            "end_frame":     self.end_frame,
            "start_ms":      self.start_ms,
            "end_ms":        self.end_ms,
            "confidence":    self.confidence,
            "rule_name":     "temporal_pose_analysis",
            "evidence": {
                **self.evidence,
                "pose_confidence":      self.pose_confidence,
                "temporal_confidence":  self.temporal_confidence,
                "supporting_frames":    self.supporting_frames,
                "state_sequence":       self.state_sequence,
                "reason":               self.reason,
                "data_source":          "IMPLEMENTED — NOT YET VALIDATED on real footage",
            },
        }


@dataclass
class _FrameFeatures:
    """Internal per-frame features used by the state machine."""
    frame_number:      int
    timestamp_ms:      float
    candidate_state:   str      # what state THIS frame suggests
    body_height:       float
    aspect_ratio:      float
    horiz_disp:        float    # lateral movement from previous frame
    pose_conf:         float


# ── Temporal Pose Analyzer ────────────────────────────────────────────────────

class TemporalPoseAnalyzer:
    """
    Accumulates per-frame pose observations for one tracked person.
    Detects sustained temporal activities with hysteresis gating.

    One instance per track_id. Feed frames in chronological order.

    Example:
        analyzer = TemporalPoseAnalyzer(track_id=1)
        for frame in frames:
            event = analyzer.update(pose_frame)
            if event:
                handle_event(event)
        final_events = analyzer.flush()
    """

    def __init__(
        self,
        track_id: int,
        window_size: int = 20,
        min_frames_crawling: int = 5,
        min_frames_crouching: int = 3,
        min_frames_running: int = 4,
        min_frames_fallen: int = 2,
        min_frames_sitting: int = 8,
        hysteresis_frames: int = 2,
    ) -> None:
        """
        Args:
            track_id:             The track this analyzer follows.
            window_size:          Sliding window size for feature averaging.
            min_frames_crawling:  Consecutive frames required to confirm crawling.
            min_frames_crouching: Consecutive frames required to confirm crouching.
            min_frames_running:   Consecutive frames required to confirm running.
            min_frames_fallen:    Consecutive frames required to confirm fallen.
            min_frames_sitting:   Consecutive frames required to confirm sitting.
            hysteresis_frames:    Minimum consecutive frames before state flip.
        """
        self.track_id = track_id
        self._window_size = window_size
        self._min = {
            STATE_CRAWLING:  min_frames_crawling,
            STATE_CROUCHING: min_frames_crouching,
            STATE_RUNNING:   min_frames_running,
            STATE_FALLEN:    min_frames_fallen,
            STATE_SITTING:   min_frames_sitting,
            STATE_WALKING:   2,
            STATE_STANDING:  1,
        }
        self._hysteresis = hysteresis_frames

        # State tracking
        self._current_state: str = STATE_UNKNOWN
        self._consecutive_in_candidate: int = 0
        self._candidate_state: str = STATE_UNKNOWN
        self._state_start_frame: int = 0
        self._state_start_ms: float = 0.0
        self._state_sequence: list[str] = []

        # Frame history
        self._feature_window: deque[_FrameFeatures] = deque(maxlen=window_size)
        self._all_frames: list[_FrameFeatures] = []
        self._prev_centroid_x: Optional[float] = None

        # Events emitted
        self._emitted_events: list[PoseEvent] = []

    # ── Public API ────────────────────────────────────────────────────────

    def update(
        self,
        pose_frame: SimplePoseFrame,
    ) -> Optional[PoseEvent]:
        """
        Feed one frame's pose observation for this track.

        Returns a PoseEvent if a sustained activity is confirmed, else None.
        """
        # Compute lateral displacement from previous frame
        horiz_disp = 0.0
        if self._prev_centroid_x is not None:
            horiz_disp = abs(pose_frame.centroid_x - self._prev_centroid_x)
        self._prev_centroid_x = pose_frame.centroid_x

        # Classify this frame's candidate state
        candidate = self._classify_frame(
            pose_frame.body_height_ratio,
            pose_frame.bbox_aspect_ratio,
            horiz_disp,
            pose_frame.torso_angle_deg,
        )

        features = _FrameFeatures(
            frame_number=pose_frame.frame_number,
            timestamp_ms=pose_frame.timestamp_ms,
            candidate_state=candidate,
            body_height=pose_frame.body_height_ratio,
            aspect_ratio=pose_frame.bbox_aspect_ratio,
            horiz_disp=horiz_disp,
            pose_conf=pose_frame.pose_confidence,
        )
        self._feature_window.append(features)
        self._all_frames.append(features)

        # Apply hysteresis gating
        return self._update_state_machine(features)

    def flush(self) -> list[PoseEvent]:
        """
        Call at end of video to flush any pending confirmed state.

        Returns list of PoseEvents (may be empty).
        """
        events: list[PoseEvent] = []

        # If we've been in a sustained non-STANDING state, emit it
        if (
            self._current_state not in (STATE_UNKNOWN, STATE_STANDING, STATE_WALKING)
            and self._state_start_frame > 0
            and self._all_frames
        ):
            last = self._all_frames[-1]
            event = self._build_event(
                self._current_state,
                self._state_start_frame,
                last.frame_number,
                self._state_start_ms,
                last.timestamp_ms,
            )
            if event:
                events.append(event)

        return events

    @property
    def current_state(self) -> str:
        return self._current_state

    # ── Internal ──────────────────────────────────────────────────────────

    def _classify_frame(
        self,
        body_height: float,
        aspect_ratio: float,
        horiz_disp: float,
        torso_angle: Optional[float],
    ) -> str:
        """Classify a single frame into a candidate pose state."""

        # Priority 1: FALLEN — sudden horizontal body
        if aspect_ratio >= _ASPECT_RATIO_HORIZONTAL and body_height < _BODY_HEIGHT_FALLEN_MAX:
            return STATE_FALLEN

        # Priority 2: CRAWLING — low body height + lateral movement
        if (
            body_height < _BODY_HEIGHT_CRAWLING_MAX
            and horiz_disp >= _HORIZONTAL_DISP_CRAWLING
        ):
            return STATE_CRAWLING

        # Priority 3: CROUCHING — low body height, little movement
        if body_height < _BODY_HEIGHT_CROUCHING_MAX:
            return STATE_CROUCHING

        # Priority 4: LOWERING — body height decreasing (transitional)
        # Check if recent frames show decreasing body height
        if len(self._feature_window) >= 3:
            recent_heights = [f.body_height for f in list(self._feature_window)[-3:]]
            if recent_heights[-1] < recent_heights[0] - 0.03:  # 3% drop over 3 frames
                return STATE_LOWERING

        # Priority 5: RUNNING — fast lateral movement
        if horiz_disp >= _HORIZONTAL_DISP_RUNNING:
            return STATE_RUNNING

        # Priority 6: WALKING — moderate lateral movement
        if horiz_disp >= _HORIZONTAL_DISP_WALKING:
            return STATE_WALKING

        # Default: STANDING
        if body_height >= _BODY_HEIGHT_STANDING_MIN:
            return STATE_STANDING

        return STATE_UNKNOWN

    def _update_state_machine(self, features: _FrameFeatures) -> Optional[PoseEvent]:
        """
        Hysteresis-gated state machine.

        A new state is accepted only after hysteresis_frames consecutive
        frames agree. This prevents single noisy frames from triggering
        state transitions.
        """
        candidate = features.candidate_state
        event_out: Optional[PoseEvent] = None

        if candidate == self._candidate_state:
            self._consecutive_in_candidate += 1
        else:
            # New candidate — reset counter
            self._candidate_state = candidate
            self._consecutive_in_candidate = 1

        # Check if candidate has enough consecutive frames to flip state
        required = self._hysteresis
        if self._consecutive_in_candidate >= required:
            if candidate != self._current_state:
                # State transition accepted
                prev_state = self._current_state

                # Emit event if leaving an interesting state
                if (
                    prev_state not in (STATE_UNKNOWN, STATE_STANDING, STATE_WALKING)
                    and self._state_start_frame > 0
                ):
                    event_out = self._build_event(
                        prev_state,
                        self._state_start_frame,
                        features.frame_number,
                        self._state_start_ms,
                        features.timestamp_ms,
                    )

                # Record state transition
                if prev_state != STATE_UNKNOWN:
                    self._state_sequence.append(prev_state)

                self._current_state = candidate
                self._state_start_frame = features.frame_number
                self._state_start_ms = features.timestamp_ms
                self._consecutive_in_candidate = 0

        # Also emit running events in real-time (don't wait for transition)
        if (
            self._current_state == STATE_RUNNING
            and features.candidate_state == STATE_RUNNING
        ):
            # Running events are emitted after min_frames to avoid false positives
            running_frames = [
                f for f in list(self._feature_window)
                if f.candidate_state == STATE_RUNNING
            ]
            if len(running_frames) == self._min[STATE_RUNNING]:
                # Exactly at threshold — emit
                event_out = self._build_event(
                    STATE_RUNNING,
                    running_frames[0].frame_number,
                    running_frames[-1].frame_number,
                    running_frames[0].timestamp_ms,
                    running_frames[-1].timestamp_ms,
                )

        if event_out:
            self._emitted_events.append(event_out)
        return event_out

    def _build_event(
        self,
        state: str,
        start_frame: int,
        end_frame: int,
        start_ms: float,
        end_ms: float,
    ) -> Optional[PoseEvent]:
        """Build a PoseEvent for the given state if it meets duration requirements."""

        # Get frames that contributed to this state
        supporting = [
            f.frame_number for f in self._all_frames
            if start_frame <= f.frame_number <= end_frame
            and f.candidate_state == state
        ]

        min_required = self._min.get(state, 1)
        if len(supporting) < min_required:
            return None

        # Compute average metrics
        relevant = [f for f in self._all_frames if f.frame_number in supporting]
        avg_height = sum(f.body_height for f in relevant) / max(len(relevant), 1)
        avg_disp = sum(f.horiz_disp for f in relevant) / max(len(relevant), 1)
        avg_pose_conf = sum(f.pose_conf for f in relevant) / max(len(relevant), 1)
        temporal_conf = len(supporting) / max(end_frame - start_frame + 1, 1)

        # Map state to event type
        state_to_event = {
            STATE_CRAWLING:  "person_crawling",
            STATE_CROUCHING: "person_crouching_sustained",
            STATE_FALLEN:    "person_falling_likely",
            STATE_RUNNING:   "person_running",
            STATE_SITTING:   "person_loitering",  # sitting treated as loitering for now
        }
        event_type = state_to_event.get(state)
        if not event_type:
            return None

        # Compute overall confidence
        # Penalise low temporal_confidence and low pose_confidence
        base_confidence = min(len(supporting) / max(min_required * 2, 1), 1.0)
        confidence = round(
            base_confidence * max(temporal_conf, 0.3) * max(avg_pose_conf, 0.2) + 0.1,
            3,
        )
        confidence = min(confidence, 0.95)  # never claim 100%

        # Build reason string
        reason_parts = [
            f"{len(supporting)} frames with {state} posture",
            f"avg body height={avg_height:.2%}",
            f"avg lateral displacement={avg_disp:.3%}/frame",
        ]
        reason = "; ".join(reason_parts)

        return PoseEvent(
            event_type=event_type,
            track_id=self.track_id,
            start_frame=start_frame,
            end_frame=end_frame,
            start_ms=start_ms,
            end_ms=end_ms,
            confidence=confidence,
            pose_confidence=round(avg_pose_conf, 3),
            temporal_confidence=round(temporal_conf, 3),
            supporting_frames=supporting,
            state_sequence=list(self._state_sequence),
            reason=reason,
            evidence={
                "avg_body_height_ratio": round(avg_height, 4),
                "avg_lateral_disp":      round(avg_disp, 5),
                "state":                 state,
                "classification_note": (
                    "IMPLEMENTED — thresholds not calibrated against real footage. "
                    "Treat confidence as relative, not absolute."
                ),
            },
        )
