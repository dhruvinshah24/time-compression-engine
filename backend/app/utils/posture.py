"""
Posture Analyzer — Detect sitting, standing-up transitions from bbox geometry.

The key insight: a person's bounding box shape changes predictably with posture.

Standing:  height >> width  → aspect ratio (h/w) typically 2.0 – 3.5
Crouching: height ≈ width   → aspect ratio 1.0 – 1.8
Sitting:   height < baseline by 30-50%, bbox center moves DOWN in frame

Algorithm:
  1. Compute per-observation bbox metrics: height, width, aspect_ratio, cy (center-y)
  2. Establish a "standing baseline" from the first confirmed standing frames
  3. Detect when aspect_ratio drops below threshold → SITTING
  4. Detect when aspect_ratio recovers → STANDING_UP

This is purely geometric — no pose estimation model needed.
Works for typical CCTV footage where the person is viewed from a fixed angle.

Limitations:
  - Does not work for overhead cameras (person always looks foreshortened)
  - May misfire if person walks partially out of frame (partial bbox)
  - Requires ≥ 3 observations on the track for reliable baseline
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# COCO class IDs for objects we care about
INTERACTIVE_CLASSES = frozenset({
    "chair", "bench", "couch", "sofa",
    "dining table", "desk", "table",
    "laptop", "keyboard", "mouse",
    "tv", "monitor", "screen",
    "light", "lamp",
    "door", "window",
})


@dataclass
class PostureObservation:
    """Derived metrics for one bbox observation."""
    frame_number: int
    timestamp_ms: float
    aspect_ratio: float   # height / width
    bbox_height: float    # normalized [0, 1] relative to frame height
    center_y: float       # normalized [0, 1], 0=top, 1=bottom of frame
    width_norm: float     # normalized width
    height_norm: float    # normalized height


@dataclass
class PostureEvent:
    """A detected posture transition."""
    event_type: str         # "person_sitting" | "person_standing_up"
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float
    track_id: int
    confidence: float
    evidence: dict = field(default_factory=dict)


@dataclass
class ObjectProximityEvent:
    """Person detected near/interacting with a known object class."""
    event_type: str         # "person_near_chair" | "person_interaction" etc.
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float
    track_id: int
    object_class: str
    confidence: float
    evidence: dict = field(default_factory=dict)


def _get_frame_dims(frame_path: str) -> tuple[int, int]:
    """Return (width, height) of a frame image. Falls back to (640, 480)."""
    try:
        from PIL import Image
        with Image.open(frame_path) as img:
            return img.size  # (width, height)
    except Exception:
        return (640, 480)


def analyze_posture(
    track,
    frame_width: int = 848,
    frame_height: int = 478,
    sitting_aspect_ratio_drop: float = 0.60,
    min_standing_aspect_ratio: float = 1.60,
    min_observations: int = 4,
) -> list[PostureEvent]:
    """
    Detect sitting / standing-up transitions for a person track.

    Args:
        track: Track object with .observations list.
        frame_width: Frame width in pixels (for normalization).
        frame_height: Frame height in pixels (for normalization).
        sitting_aspect_ratio_drop: Fraction of baseline below which person is
            considered sitting (e.g. 0.60 = ratio drops to 60% of baseline).
        min_standing_aspect_ratio: Minimum aspect ratio for "standing" baseline.
            Prevents establishing a sitting position as the baseline.
        min_observations: Minimum observations required.

    Returns:
        List of PostureEvent (may be empty).
    """
    obs_list = track.observations
    if len(obs_list) < min_observations:
        return []

    # Compute per-observation metrics
    posture_obs: list[PostureObservation] = []
    for obs in obs_list:
        b = obs.bbox
        w = b.x2 - b.x1
        h = b.y2 - b.y1
        if w <= 0 or h <= 0:
            continue
        ar = h / w
        posture_obs.append(PostureObservation(
            frame_number=obs.frame_number,
            timestamp_ms=obs.timestamp_ms,
            aspect_ratio=ar,
            bbox_height=h / frame_height,
            center_y=(b.y1 + b.y2) / 2 / frame_height,
            width_norm=w / frame_width,
            height_norm=h / frame_height,
        ))

    if len(posture_obs) < min_observations:
        return []

    # Establish baseline from first 25% of observations that look like standing
    # (aspect ratio above min_standing_aspect_ratio)
    baseline_count = max(2, len(posture_obs) // 4)
    baseline_candidates = [
        p.aspect_ratio for p in posture_obs[:baseline_count]
        if p.aspect_ratio >= min_standing_aspect_ratio
    ]
    if not baseline_candidates:
        # No clear standing baseline — take median of first quarter
        baseline_candidates = [p.aspect_ratio for p in posture_obs[:baseline_count]]

    baseline_ar = sum(baseline_candidates) / len(baseline_candidates)

    # Only proceed if baseline looks like a standing person
    if baseline_ar < min_standing_aspect_ratio:
        logger.debug(
            "Track %d: baseline aspect ratio %.2f too low for sitting detection",
            track.track_id, baseline_ar,
        )
        return []

    sitting_threshold = baseline_ar * sitting_aspect_ratio_drop

    # State machine: detect SITTING / STANDING_UP transitions
    events: list[PostureEvent] = []
    is_sitting = False
    sit_start_obs: PostureObservation | None = None

    CONSECUTIVE_REQUIRED = 2  # Need N consecutive frames to confirm transition

    sitting_buffer: list[PostureObservation] = []
    standing_buffer: list[PostureObservation] = []

    for p in posture_obs:
        if not is_sitting:
            if p.aspect_ratio < sitting_threshold:
                sitting_buffer.append(p)
                standing_buffer.clear()
                if len(sitting_buffer) >= CONSECUTIVE_REQUIRED:
                    is_sitting = True
                    sit_start_obs = sitting_buffer[0]
                    confidence = min(
                        0.90,
                        0.55 + (baseline_ar - p.aspect_ratio) / baseline_ar * 0.35
                    )
                    events.append(PostureEvent(
                        event_type="person_sitting",
                        start_frame=sit_start_obs.frame_number,
                        end_frame=p.frame_number,
                        start_ms=sit_start_obs.timestamp_ms,
                        end_ms=p.timestamp_ms,
                        track_id=track.track_id,
                        confidence=round(confidence, 4),
                        evidence={
                            "baseline_aspect_ratio": round(baseline_ar, 3),
                            "current_aspect_ratio": round(p.aspect_ratio, 3),
                            "sitting_threshold": round(sitting_threshold, 3),
                            "drop_percent": round(
                                (baseline_ar - p.aspect_ratio) / baseline_ar * 100, 1
                            ),
                        },
                    ))
            else:
                sitting_buffer.clear()

        else:  # Currently sitting
            recovery_threshold = baseline_ar * 0.80  # Allow some slack
            if p.aspect_ratio >= recovery_threshold:
                standing_buffer.append(p)
                sitting_buffer.clear()
                if len(standing_buffer) >= CONSECUTIVE_REQUIRED:
                    is_sitting = False
                    stand_start = standing_buffer[0]
                    duration_sitting_ms = (
                        stand_start.timestamp_ms - sit_start_obs.timestamp_ms
                        if sit_start_obs else 0.0
                    )
                    events.append(PostureEvent(
                        event_type="person_standing_up",
                        start_frame=stand_start.frame_number,
                        end_frame=p.frame_number,
                        start_ms=stand_start.timestamp_ms,
                        end_ms=p.timestamp_ms,
                        track_id=track.track_id,
                        confidence=0.80,
                        evidence={
                            "duration_sitting_ms": round(duration_sitting_ms, 1),
                            "recovery_aspect_ratio": round(p.aspect_ratio, 3),
                        },
                    ))
                    standing_buffer.clear()
            else:
                standing_buffer.clear()

    return events


def detect_object_interactions(
    person_track,
    all_tracks: list,
    frame_width: int = 848,
    frame_height: int = 478,
    proximity_threshold: float = 0.25,  # fraction of frame width
) -> list[ObjectProximityEvent]:
    """
    Detect when a person track is in proximity to interactive objects.

    Uses bounding box proximity (not IoU) — object and person don't need
    to overlap, just be nearby. This handles scenarios like:
      - Person standing next to a chair before sitting
      - Person near a desk/table while working

    Args:
        person_track:        The person Track to analyze.
        all_tracks:          All confirmed tracks (including chairs etc).
        frame_width:         Frame dimensions for normalization.
        proximity_threshold: Max normalized distance between bbox centers
                             to count as "near" (0.25 = 1/4 of frame width).

    Returns:
        List of ObjectProximityEvent.
    """
    # Only analyze person tracks
    if person_track.class_name != "person":
        return []

    # Find object tracks we care about
    object_tracks = [
        t for t in all_tracks
        if t.class_name in INTERACTIVE_CLASSES
        and t.track_id != person_track.track_id
    ]

    if not object_tracks:
        return []

    events: list[ObjectProximityEvent] = []

    for obj_track in object_tracks:
        # Build frame-number → bbox lookup for the object
        obj_bbox_by_frame: dict[int, object] = {
            obs.frame_number: obs.bbox for obs in obj_track.observations
        }
        if not obj_bbox_by_frame:
            continue

        # Find frames where person is near this object
        near_frames: list[tuple[int, float, float]] = []  # (frame, timestamp, dist)
        for obs in person_track.observations:
            if obs.frame_number not in obj_bbox_by_frame:
                # Find closest frame in object track
                closest_fn = min(
                    obj_bbox_by_frame.keys(),
                    key=lambda fn: abs(fn - obs.frame_number)
                )
                obj_bbox = obj_bbox_by_frame[closest_fn]
            else:
                obj_bbox = obj_bbox_by_frame[obs.frame_number]

            # Person bbox center
            pb = obs.bbox
            pcx = (pb.x1 + pb.x2) / 2 / frame_width
            pcy = (pb.y1 + pb.y2) / 2 / frame_height

            # Object bbox center
            ocx = (obj_bbox.x1 + obj_bbox.x2) / 2 / frame_width
            ocy = (obj_bbox.y1 + obj_bbox.y2) / 2 / frame_height

            dist = ((pcx - ocx) ** 2 + (pcy - ocy) ** 2) ** 0.5
            if dist <= proximity_threshold:
                near_frames.append((obs.frame_number, obs.timestamp_ms, dist))

        if len(near_frames) < 2:
            continue

        # Group consecutive near-frames into interaction events
        interactions = _group_consecutive(near_frames, max_gap_frames=10)
        for interaction in interactions:
            if len(interaction) < 2:
                continue
            start_fn, start_ms, _ = interaction[0]
            end_fn, end_ms, _ = interaction[-1]
            avg_dist = sum(d for _, _, d in interaction) / len(interaction)
            confidence = min(0.85, 0.50 + (1.0 - avg_dist / proximity_threshold) * 0.35)
            event_type = f"person_near_{obj_track.class_name.replace(' ', '_')}"
            events.append(ObjectProximityEvent(
                event_type=event_type,
                start_frame=start_fn,
                end_frame=end_fn,
                start_ms=start_ms,
                end_ms=end_ms,
                track_id=person_track.track_id,
                object_class=obj_track.class_name,
                confidence=round(confidence, 4),
                evidence={
                    "avg_normalized_distance": round(avg_dist, 4),
                    "proximity_threshold": proximity_threshold,
                    "frames_near": len(interaction),
                    "object_track_id": obj_track.track_id,
                },
            ))

    return events


def _group_consecutive(
    frames: list[tuple[int, float, float]],
    max_gap_frames: int,
) -> list[list[tuple[int, float, float]]]:
    """Group frame observations into runs where gaps don't exceed max_gap_frames."""
    if not frames:
        return []
    groups: list[list] = [[frames[0]]]
    for item in frames[1:]:
        fn = item[0]
        if fn - groups[-1][-1][0] <= max_gap_frames:
            groups[-1].append(item)
        else:
            groups.append([item])
    return groups
