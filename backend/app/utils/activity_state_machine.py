"""
Activity State Machine — Time Compression Engine.

The core problem with frame-by-frame event emission is noise:
a "person_reaching_up" fires every frame the wrist is high, producing
5 identical events in 5 seconds that mean nothing to a human viewer.

This module implements a proper state machine over the person track
that produces events ONLY on state transitions:

    ENTERING → WALKING → STANDING → SITTING → STANDING → EXITING

Key inputs (all from prior pipeline stages, no new ML needed):
  - person_track.observations  (TrackObservation list from s05)
  - chair_tracks               (Track list for class_name=="chair" from s05)
  - frame_poses                (optional FramePose list from s07 Pass 3)
  - brightness_events          (LightingEvent list from s07 Pass 2)

Algorithm:
  For each consecutive pair of person track observations:
    1. Compute velocity (centroid displacement / Δt)
    2. Compute spatial proximity to chair tracks
    3. Use rolling window of pose labels if available
    4. Apply transition rules (see TRANSITION_RULES below)
    5. Emit one event per state transition (not per frame)

Output: a chronologically ordered list of ActivityEvent objects,
one per state transition — no duplicates, no noise.

TRANSITION_RULES:
  ENTERING:
    - Any new person detection → immediately emit person_entered_scene

  WALKING:
    - velocity > WALK_VELOCITY_THRESHOLD (normalized units/sec)

  STANDING:
    - velocity < STILL_VELOCITY_THRESHOLD
    - Not near chair
    - Person not at frame edge

  SITTING:
    - velocity < STILL_VELOCITY_THRESHOLD
    - Near chair OR pose says sitting
    - Center Y moved downward compared to standing baseline

  STANDING_UP (transition from SITTING):
    - Was SITTING
    - velocity > STILL_VELOCITY_THRESHOLD OR center Y rose

  EXITING:
    - Person near frame edge AND moving away
    - OR track ends (ENDED state)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engines.perception.tracker.track import Track, TrackObservation
    from app.utils.pose_estimate import FramePose

from app.engines.semantic.event_understanding.rules import EventType

logger = logging.getLogger(__name__)

# ── Tuning constants (FPS-ADAPTIVE) ─────────────────────────────────────────────
# All velocity thresholds are in NORMALISED COORDINATE UNITS PER SECOND.
# This makes them FPS-independent: the same values work whether
# frame_skip=3 (10fps effective at 30fps) or frame_skip=5 (6fps effective).
#
# Calibration at 10fps effective, 848px frame width:
#   Person walking 1 m/s in 5m room ≈ 0.17 normalised cx/s
#   Person standing (micro-jitter) ≈ 0.02–0.04 cx/s
#   Person running 3 m/s ≈ 0.50 normalised cx/s
#
WALK_VELOCITY_THRESHOLD   = 0.08    # normalised units/second — walking starts here
STILL_VELOCITY_THRESHOLD  = 0.03    # below this = standing or sitting
EDGE_MARGIN               = 0.12    # 12% from any edge = "at edge"
CHAIR_PROXIMITY_NORM      = 0.28    # within 28% frame width = near chair
SITTING_CY_DROP           = 0.04    # center Y must drop by 4% to confirm sitting
SMOOTHING_WINDOW          = 5       # observations to smooth velocity over

# Loiter: person stationary for this many real seconds
LOITER_STILL_SECS         = 10.0


# ── State & Event dataclasses ─────────────────────────────────────────────────

class ActivityState(str, Enum):
    IDLE           = "idle"
    ENTERING       = "entering"
    WALKING        = "walking"
    STANDING       = "standing"
    SITTING        = "sitting"
    EXITING        = "exiting"


@dataclass
class ActivityEvent:
    """A semantic event emitted by the state machine on a state transition."""
    event_type: str
    track_id: int
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float
    confidence: float
    evidence: dict = field(default_factory=dict)


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _velocity_per_sec(
    obs_a: "TrackObservation",
    obs_b: "TrackObservation",
    fps: float = 30.0,
    frame_skip: int = 3,
) -> float:
    """
    Return Euclidean velocity in normalised-coordinate units PER SECOND.
    FPS-adaptive: (displacement / frames_elapsed) * effective_fps.
    effective_fps = fps / frame_skip  (how many original frames per observation).
    """
    dx = obs_b.bbox.cx - obs_a.bbox.cx
    dy = obs_b.bbox.cy - obs_a.bbox.cy
    dist = (dx * dx + dy * dy) ** 0.5
    d_frames = max(1, obs_b.frame_number - obs_a.frame_number)
    # Convert frame displacement to time in seconds
    d_seconds = d_frames / max(fps, 1.0)
    return dist / max(d_seconds, 1e-6)


# Keep old name as alias for backward compat inside this file
def _velocity(obs_a: "TrackObservation", obs_b: "TrackObservation") -> float:
    return _velocity_per_sec(obs_a, obs_b)


def _smooth_velocity(
    observations: list["TrackObservation"],
    idx: int,
    window: int,
    fps: float = 30.0,
) -> float:
    """Rolling mean velocity (units/sec) over a window of observations ending at idx."""
    start = max(0, idx - window)
    if idx <= start:
        return 0.0
    vels = [
        _velocity_per_sec(observations[i], observations[i + 1], fps=fps)
        for i in range(start, idx)
        if i + 1 < len(observations)
    ]
    return sum(vels) / len(vels) if vels else 0.0


def _is_at_edge(obs: "TrackObservation", margin: float = EDGE_MARGIN) -> bool:
    """Return True if the bounding box centroid is near any frame edge."""
    cx, cy = obs.bbox.cx, obs.bbox.cy
    return (cx < margin or cx > 1.0 - margin
            or cy < margin or cy > 1.0 - margin)


def _near_any_chair(obs: "TrackObservation",
                    chair_centroids: list[tuple[float, float]],
                    threshold: float = CHAIR_PROXIMITY_NORM) -> tuple[bool, float]:
    """
    Return (is_near, distance) to the closest chair.
    chair_centroids: list of (cx, cy) for all confirmed chair tracks.
    """
    if not chair_centroids:
        return False, 999.0
    best = min(
        ((obs.bbox.cx - ccx) ** 2 + (obs.bbox.cy - ccy) ** 2) ** 0.5
        for ccx, ccy in chair_centroids
    )
    return best < threshold, best


def _get_chair_centroids(all_tracks: list["Track"]) -> list[tuple[float, float]]:
    """
    Extract centroid positions of all confirmed chair/seat tracks.
    Uses the median observation centroid for stability.
    """
    SEAT_CLASSES = {"chair", "office_chair", "couch", "bench", "sofa", "stool", "ottoman"}
    centroids = []
    for t in all_tracks:
        if (t.class_name or "").lower() not in SEAT_CLASSES:
            continue
        if not t.observations:
            continue
        cxs = [o.bbox.cx for o in t.observations]
        cys = [o.bbox.cy for o in t.observations]
        cxs.sort(); cys.sort()
        mid = len(cxs) // 2
        centroids.append((cxs[mid], cys[mid]))
    return centroids



def _pose_label_at_frame(
    frame_poses: list["FramePose"],
    frame_number: int,
    window: int = 3,
) -> str | None:
    """
    Return dominant pose label in a window around frame_number.
    Returns: "sitting" | "walking" | "standing" | None
    """
    if not frame_poses:
        return None
    nearby = [p for p in frame_poses
              if abs(p.frame_number - frame_number) <= window]
    if not nearby:
        return None
    sitting_count = sum(1 for p in nearby if p.is_sitting)
    walking_count = sum(1 for p in nearby if p.is_walking)
    standing_count = sum(1 for p in nearby if p.is_standing)
    total = len(nearby)
    if sitting_count / total > 0.5:
        return "sitting"
    if walking_count / total > 0.4:
        return "walking"
    if standing_count / total > 0.4:
        return "standing"
    return None


# ── Core state machine ────────────────────────────────────────────────────────

def run_activity_state_machine(
    person_track: "Track",
    all_tracks: list["Track"],
    frame_poses: list["FramePose"] | None = None,
    fps: float = 30.0,
) -> list[ActivityEvent]:
    """
    Run the activity state machine over a person track.

    Args:
        person_track:  A confirmed Track with class_name=="person".
        all_tracks:    All confirmed tracks (to find chairs, desks, etc.)
        frame_poses:   Optional pose analysis output from s07 Pass 3.
        fps:           Video FPS (used to convert frames to time).

    Returns:
        List of ActivityEvent objects, one per state transition.
        Guaranteed to have at most one event of each type per
        contiguous activity block.
    """
    obs = sorted(person_track.observations, key=lambda o: o.frame_number)
    if not obs:
        return []

    chair_centroids = _get_chair_centroids(all_tracks)
    frame_poses = frame_poses or []

    events: list[ActivityEvent] = []
    state = ActivityState.IDLE

    # State entry data
    state_start_obs = obs[0]
    standing_cy: float | None = None  # reference height when person was standing

    # Emit enter event
    events.append(ActivityEvent(
        event_type=EventType.PERSON_ENTERED_SCENE,
        track_id=person_track.track_id,
        start_frame=obs[0].frame_number,
        end_frame=obs[0].frame_number,
        start_ms=obs[0].timestamp_ms,
        end_ms=obs[0].timestamp_ms,
        confidence=0.90,
        evidence={
            "entry_cx": round(obs[0].bbox.cx, 3),
            "entry_cy": round(obs[0].bbox.cy, 3),
            "at_edge": _is_at_edge(obs[0]),
            "source": "state_machine",
        },
    ))
    state = ActivityState.ENTERING
    state_start_obs = obs[0]

    for i in range(1, len(obs)):
        o = obs[i]
        vel = _smooth_velocity(obs, i, SMOOTHING_WINDOW, fps=fps)
        near_chair, chair_dist = _near_any_chair(o, chair_centroids)
        at_edge = _is_at_edge(o)
        pose_label = _pose_label_at_frame(frame_poses, o.frame_number)

        # ── State transitions ─────────────────────────────────────────────

        if state == ActivityState.ENTERING:
            if vel >= WALK_VELOCITY_THRESHOLD:
                state = ActivityState.WALKING
                state_start_obs = o
            elif vel < STILL_VELOCITY_THRESHOLD:
                if near_chair or pose_label == "sitting":
                    state = ActivityState.SITTING
                    standing_cy = o.bbox.cy - SITTING_CY_DROP
                    events.append(ActivityEvent(
                        event_type=EventType.PERSON_SITTING,
                        track_id=person_track.track_id,
                        start_frame=o.frame_number,
                        end_frame=o.frame_number,
                        start_ms=o.timestamp_ms,
                        end_ms=o.timestamp_ms,
                        confidence=0.80,
                        evidence={
                            "velocity": round(vel, 5),
                            "near_chair": near_chair,
                            "chair_dist": round(chair_dist, 3),
                            "cx": round(o.bbox.cx, 3),
                            "cy": round(o.bbox.cy, 3),
                            "pose": pose_label,
                            "source": "state_machine",
                        },
                    ))
                else:
                    state = ActivityState.STANDING
                    standing_cy = o.bbox.cy
                state_start_obs = o

        elif state == ActivityState.WALKING:
            if vel < STILL_VELOCITY_THRESHOLD:
                # Stopped moving — sitting or standing?
                if near_chair or pose_label == "sitting":
                    state = ActivityState.SITTING
                    standing_cy = o.bbox.cy - SITTING_CY_DROP
                    events.append(ActivityEvent(
                        event_type=EventType.PERSON_SITTING,
                        track_id=person_track.track_id,
                        start_frame=o.frame_number,
                        end_frame=o.frame_number,
                        start_ms=o.timestamp_ms,
                        end_ms=o.timestamp_ms,
                        confidence=0.85,
                        evidence={
                            "velocity": round(vel, 5),
                            "near_chair": near_chair,
                            "chair_dist": round(chair_dist, 3),
                            "pose": pose_label,
                            "source": "state_machine",
                        },
                    ))
                else:
                    state = ActivityState.STANDING
                    standing_cy = o.bbox.cy
                    events.append(ActivityEvent(
                        event_type=EventType.PERSON_STANDING,
                        track_id=person_track.track_id,
                        start_frame=o.frame_number,
                        end_frame=o.frame_number,
                        start_ms=o.timestamp_ms,
                        end_ms=o.timestamp_ms,
                        confidence=0.75,
                        evidence={
                            "velocity": round(vel, 5),
                            "cx": round(o.bbox.cx, 3),
                            "cy": round(o.bbox.cy, 3),
                            "source": "state_machine",
                        },
                    ))
                state_start_obs = o

        elif state == ActivityState.STANDING:
            if vel >= WALK_VELOCITY_THRESHOLD:
                if at_edge:
                    # Moving toward edge = about to exit
                    state = ActivityState.EXITING
                else:
                    state = ActivityState.WALKING
                    events.append(ActivityEvent(
                        event_type=EventType.PERSON_WALKING,
                        track_id=person_track.track_id,
                        start_frame=o.frame_number,
                        end_frame=o.frame_number,
                        start_ms=o.timestamp_ms,
                        end_ms=o.timestamp_ms,
                        confidence=0.75,
                        evidence={
                            "velocity": round(vel, 5),
                            "source": "state_machine",
                        },
                    ))
                state_start_obs = o
            elif near_chair or pose_label == "sitting":
                state = ActivityState.SITTING
                standing_cy = o.bbox.cy - SITTING_CY_DROP
                events.append(ActivityEvent(
                    event_type=EventType.PERSON_SITTING,
                    track_id=person_track.track_id,
                    start_frame=o.frame_number,
                    end_frame=o.frame_number,
                    start_ms=o.timestamp_ms,
                    end_ms=o.timestamp_ms,
                    confidence=0.88,
                    evidence={
                        "velocity": round(vel, 5),
                        "near_chair": near_chair,
                        "chair_dist": round(chair_dist, 3),
                        "pose": pose_label,
                        "source": "state_machine",
                    },
                ))
                state_start_obs = o

        elif state == ActivityState.SITTING:
            # Check if person stood up.
            # ASM-1 FIX: Y increases DOWNWARD in image coords, so "rising" (standing
            # up) means cy DECREASING. Old check used +SITTING_CY_DROP which was
            # the opposite direction.
            cy_rose = (
                standing_cy is not None
                and o.bbox.cy < standing_cy - SITTING_CY_DROP  # cy moved UP = person rose
            )
            if (vel >= WALK_VELOCITY_THRESHOLD
                    or cy_rose
                    or (not near_chair and pose_label in ("standing", "walking"))):
                state = ActivityState.WALKING if vel >= WALK_VELOCITY_THRESHOLD else ActivityState.STANDING
                events.append(ActivityEvent(
                    event_type=EventType.PERSON_STANDING_UP,
                    track_id=person_track.track_id,
                    start_frame=o.frame_number,
                    end_frame=o.frame_number,
                    start_ms=o.timestamp_ms,
                    end_ms=o.timestamp_ms,
                    confidence=0.85 if cy_rose else 0.82,
                    evidence={
                        "velocity": round(vel, 5),
                        "near_chair": near_chair,
                        "cy_rose": cy_rose,
                        "pose": pose_label,
                        "source": "state_machine",
                    },
                ))
                standing_cy = o.bbox.cy
                state_start_obs = o

        elif state == ActivityState.EXITING:
            # ASM-2 FIX: Not an absorbing state anymore.
            # Person who walks back from the edge transitions to WALKING.
            if not at_edge and vel > STILL_VELOCITY_THRESHOLD:
                state = ActivityState.WALKING
                state_start_obs = o

    # ASM-3 FIX: Only emit PERSON_LEFT_SCENE for tracks with ≥2 observations.
    # Single-frame ghost tracks (reflections, shadows) produced spurious
    # ENTERED + LEFT pairs that cluttered the timeline.
    last = obs[-1]
    if len(obs) >= 2:
        events.append(ActivityEvent(
            event_type=EventType.PERSON_LEFT_SCENE,
            track_id=person_track.track_id,
            start_frame=last.frame_number,
            end_frame=last.frame_number,
            start_ms=last.timestamp_ms,
            end_ms=last.timestamp_ms,
            confidence=0.90 if _is_at_edge(last) else 0.75,
            evidence={
                "exit_cx": round(last.bbox.cx, 3),
                "exit_cy": round(last.bbox.cy, 3),
                "at_edge": _is_at_edge(last),
                "track_length": len(obs),
                "source": "state_machine",
            },
        ))

    logger.info(
        "State machine for track %d: %d observations → %d events: %s",
        person_track.track_id,
        len(obs),
        len(events),
        [e.event_type for e in events],
    )
    return events


# ── Event deduplication / merging ─────────────────────────────────────────────

def deduplicate_and_merge(
    events: list,
    merge_gap_ms: float = 2500.0,
) -> list:
    """
    Merge consecutive events of the same type that are within merge_gap_ms.

    This eliminates the "5× person_reaching_up in 5 seconds" noise by
    collapsing them into a single event spanning the full duration.

    Args:
        events:        Any list of objects with event_type, start_ms, end_ms attributes.
        merge_gap_ms:  Events of the same type within this gap get merged.

    Returns:
        Deduplicated list, sorted by start_ms.
    """
    if not events:
        return events

    # Group by event_type
    by_type: dict[str, list] = {}
    for e in events:
        t = getattr(e, "event_type", None) or e.get("event_type", "unknown")
        by_type.setdefault(t, []).append(e)

    merged_all = []
    for t, group in by_type.items():
        group.sort(key=lambda e: getattr(e, "start_ms", None) or e.get("start_ms", 0))
        current = [group[0]]
        for evt in group[1:]:
            last_ms = getattr(current[-1], "end_ms", None) or current[-1].get("end_ms", 0)
            this_ms = getattr(evt, "start_ms", None) or evt.get("start_ms", 0)
            if this_ms - last_ms <= merge_gap_ms:
                current.append(evt)
            else:
                merged_all.append(_merge_group(current))
                current = [evt]
        merged_all.append(_merge_group(current))

    merged_all.sort(key=lambda e: getattr(e, "start_ms", None) or e.get("start_ms", 0))
    return merged_all


def _merge_group(group: list) -> object:
    """
    Merge a list of same-type events into one, spanning start→end.
    Returns the same object type as the inputs.
    """
    if len(group) == 1:
        return group[0]

    first = group[0]
    last  = group[-1]

    # Compute max confidence in group
    confs = [getattr(e, "confidence", 0) or e.get("confidence", 0) for e in group]
    best_conf = max(confs)

    if isinstance(first, dict):
        merged = dict(first)
        merged["end_ms"] = getattr(last, "end_ms", None) or last.get("end_ms", merged.get("end_ms"))
        merged["end_frame"] = getattr(last, "end_frame", None) or last.get("end_frame", merged.get("end_frame"))
        merged["confidence"] = best_conf
        merged["evidence"] = {**(first.get("evidence") or {}), "merged_count": len(group)}
        return merged

    # Dataclass/object
    try:
        first.end_ms    = getattr(last, "end_ms", first.end_ms)
        first.end_frame = getattr(last, "end_frame", first.end_frame)
        first.confidence = best_conf
        if hasattr(first, "evidence") and isinstance(first.evidence, dict):
            first.evidence["merged_count"] = len(group)
    except (AttributeError, TypeError):
        pass
    return first
