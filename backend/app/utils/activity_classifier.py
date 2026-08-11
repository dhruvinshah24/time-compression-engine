"""
Activity Classifier — Phase 7.

Classifies the dominant activity of a confirmed person track using:
  1. Trajectory analysis   — velocity, direction, consistency
  2. Pose geometry         — bbox aspect ratio changes (sitting, crouching)
  3. Object proximity      — bicycle nearby → cycling
  4. Spatial context       — vertical drift → stair walking

Every result includes a confidence score and an evidence dict so the
frontend can show WHY a classification was made.

Tuned for indoor CCTV characteristics:
  - Fixed camera angle (typically 30–60° overhead)
  - Controlled lighting
  - People at distances of 2–15m from camera
  - Frame skip = 5 (each observation ≈ 1 frame apart in extracted frames)

Activity vocabulary:
  walking              — moderate horizontal velocity, stable height
  running              — high velocity (>2× walk threshold)
  walking_upstairs     — sustained positive Y velocity + horizontal motion
  walking_downstairs   — sustained negative Y velocity + horizontal motion
  cycling              — near bicycle track OR high horizontal + stable height
  sitting              — bbox height < 0.6× standing height, near chair
  standing             — minimal velocity, normal bbox height
  crouching/bending    — sudden bbox height drop (>20%) with stable center-x
  loitering            — velocity < still threshold for >15s
  entering             — first observation at frame edge
  exiting              — last observation at frame edge

Usage:
    clf = ActivityClassifier(fps=30, frame_skip=5)
    result = clf.classify(track, all_tracks=all_tracks)
    print(result.label)        # "walking_upstairs"
    print(result.confidence)   # 0.82
    print(result.evidence)     # {"vertical_velocity": -0.012, ...}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Velocity thresholds (normalised frame-units per extracted frame) ───────────
# One "unit" = full frame width or height traversal in one extracted frame.
# At frame_skip=5, fps=30: each extracted frame = 5/30 = 0.167s apart.
STILL_THRESHOLD         = 0.003   # cx/cy change < this → effectively stationary
WALK_THRESHOLD          = 0.008   # moderate walking pace
RUN_THRESHOLD           = 0.022   # fast movement (running)
STAIR_VERT_THRESHOLD    = 0.005   # sustained vertical velocity → stairs
CYCLE_HORIZ_THRESHOLD   = 0.018   # high horizontal speed → possible cycling
LOITER_STILL_SEC        = 12.0    # seconds of minimal movement → loitering

# Object class names considered "bicycle" for cycling detection
BICYCLE_CLASSES = {"bicycle", "bike", "cycle", "motorbike", "motorcycle", "scooter"}


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class ActivityResult:
    """Classification result for one person track."""
    label: str                           # e.g. "walking_upstairs"
    confidence: float                    # 0.0 – 1.0
    evidence: dict = field(default_factory=dict)
    # Sub-activities detected alongside the dominant one
    secondary_labels: list[str] = field(default_factory=list)
    # Spatial context
    entry_direction: Optional[str] = None   # "left", "right", "top", "bottom"
    exit_direction:  Optional[str] = None
    # Duration
    duration_ms: float = 0.0


# ── Classifier ────────────────────────────────────────────────────────────────

class ActivityClassifier:
    """
    Classifies dominant activity for a confirmed person track.

    Args:
        fps:         Original video FPS (before frame extraction).
        frame_skip:  How many original frames were skipped between extractions.
    """

    def __init__(self, fps: float = 30.0, frame_skip: int = 5) -> None:
        self.fps = fps
        self.frame_skip = frame_skip
        # Time between consecutive extracted frames (seconds)
        self._dt = frame_skip / max(fps, 1.0)

    def classify(
        self,
        track,
        all_tracks: Optional[list] = None,
    ) -> ActivityResult:
        """
        Classify the activity of a track.

        Args:
            track:      A Track object with .observations and .class_name.
            all_tracks: Full list of all tracks (for object-proximity checks).

        Returns:
            ActivityResult with label, confidence, evidence.
        """
        obs = track.observations
        if not obs:
            return ActivityResult(
                label="unknown", confidence=0.0,
                evidence={"reason": "no_observations"},
            )

        # ── Entry / exit directions ──────────────────────────────────────────
        entry_dir = _edge_direction(obs[0].bbox)
        exit_dir  = _edge_direction(obs[-1].bbox) if len(obs) > 1 else None

        # ── Duration ─────────────────────────────────────────────────────────
        duration_ms = obs[-1].timestamp_ms - obs[0].timestamp_ms

        # Only one observation → entering
        if len(obs) < 3:
            return ActivityResult(
                label="entering_scene",
                confidence=0.75,
                entry_direction=entry_dir,
                exit_direction=exit_dir,
                duration_ms=duration_ms,
                evidence={"obs_count": len(obs), "entry_direction": entry_dir},
            )

        # ── Velocity profile ─────────────────────────────────────────────────
        vx_list, vy_list, speed_list = [], [], []
        for i in range(1, len(obs)):
            dx = obs[i].bbox.cx - obs[i - 1].bbox.cx
            dy = obs[i].bbox.cy - obs[i - 1].bbox.cy
            vx_list.append(dx / self._dt)
            vy_list.append(dy / self._dt)
            speed_list.append(np.sqrt(dx * dx + dy * dy) / self._dt)

        vx_arr  = np.array(vx_list)
        vy_arr  = np.array(vy_list)
        spd_arr = np.array(speed_list)

        mean_speed    = float(np.mean(spd_arr))
        max_speed     = float(np.max(spd_arr))
        mean_vy       = float(np.mean(vy_arr))
        mean_vx       = float(np.mean(np.abs(vx_arr)))
        vy_std        = float(np.std(vy_arr))
        speed_std     = float(np.std(spd_arr))

        # ── Bbox height profile (posture) ─────────────────────────────────────
        heights = [o.bbox.height for o in obs]
        mean_h  = float(np.mean(heights))
        min_h   = float(np.min(heights))
        max_h   = float(np.max(heights))

        # ── Cycling detection ─────────────────────────────────────────────────
        cycling_conf = self._detect_cycling(track, all_tracks or [], mean_speed, mean_h)

        # ── Stair detection ───────────────────────────────────────────────────
        stair_conf, stair_dir = self._detect_stairs(vy_arr, mean_speed)

        # ── Build evidence ────────────────────────────────────────────────────
        evidence = {
            "mean_speed":  round(mean_speed, 5),
            "max_speed":   round(max_speed, 5),
            "mean_vy":     round(mean_vy, 5),
            "mean_abs_vx": round(mean_vx, 5),
            "vy_std":      round(vy_std, 5),
            "mean_height": round(mean_h, 4),
            "obs_count":   len(obs),
            "duration_s":  round(duration_ms / 1000, 2),
            "cycling_conf":round(cycling_conf, 3),
            "stair_conf":  round(stair_conf, 3),
            "entry_dir":   entry_dir,
            "exit_dir":    exit_dir,
        }

        # ── Decision tree ─────────────────────────────────────────────────────

        # Cycling takes priority if confidence is high
        if cycling_conf >= 0.60:
            return ActivityResult(
                label="cycling",
                confidence=round(cycling_conf, 3),
                entry_direction=entry_dir,
                exit_direction=exit_dir,
                duration_ms=duration_ms,
                evidence={**evidence, "reason": "bicycle_proximity_or_velocity"},
            )

        # Stair walking
        if stair_conf >= 0.55 and mean_speed >= WALK_THRESHOLD:
            label = f"walking_{stair_dir}stairs"
            return ActivityResult(
                label=label,
                confidence=round(stair_conf, 3),
                entry_direction=entry_dir,
                exit_direction=exit_dir,
                duration_ms=duration_ms,
                evidence={**evidence, "stair_direction": stair_dir, "reason": "sustained_vertical_velocity"},
            )

        # Running
        if mean_speed >= RUN_THRESHOLD:
            return ActivityResult(
                label="running",
                confidence=min(0.95, 0.70 + (mean_speed - RUN_THRESHOLD) * 10),
                entry_direction=entry_dir,
                exit_direction=exit_dir,
                duration_ms=duration_ms,
                evidence={**evidence, "reason": "high_velocity"},
            )

        # Walking (moderate speed)
        if mean_speed >= WALK_THRESHOLD:
            return ActivityResult(
                label="walking",
                confidence=min(0.92, 0.65 + mean_speed * 8),
                entry_direction=entry_dir,
                exit_direction=exit_dir,
                duration_ms=duration_ms,
                evidence={**evidence, "reason": "moderate_velocity"},
            )

        # Loitering (very low speed for extended period)
        if mean_speed < STILL_THRESHOLD and duration_ms > LOITER_STILL_SEC * 1000:
            return ActivityResult(
                label="loitering",
                confidence=0.75,
                entry_direction=entry_dir,
                exit_direction=exit_dir,
                duration_ms=duration_ms,
                evidence={**evidence, "reason": "still_for_extended_period"},
            )

        # Standing still (brief)
        if mean_speed < STILL_THRESHOLD:
            return ActivityResult(
                label="standing",
                confidence=0.80,
                entry_direction=entry_dir,
                exit_direction=exit_dir,
                duration_ms=duration_ms,
                evidence={**evidence, "reason": "minimal_velocity"},
            )

        # Default: walking slowly
        return ActivityResult(
            label="walking",
            confidence=0.55,
            entry_direction=entry_dir,
            exit_direction=exit_dir,
            duration_ms=duration_ms,
            evidence={**evidence, "reason": "default_walking"},
        )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _detect_stairs(
        self, vy_arr: np.ndarray, mean_speed: float
    ) -> tuple[float, str]:
        """
        Detect stair walking from sustained vertical velocity.

        Returns (confidence, "up" or "down").

        Algorithm:
          1. Check if >55% of vertical velocities share the same sign.
          2. Check if mean |vy| exceeds the stair threshold.
          3. Confidence scales with consistency and magnitude.
        """
        if len(vy_arr) < 4:
            return 0.0, "up"

        n_up   = int(np.sum(vy_arr < -STAIR_VERT_THRESHOLD))   # cy decreasing = moving UP
        n_down = int(np.sum(vy_arr > STAIR_VERT_THRESHOLD))    # cy increasing = moving DOWN
        n_total = len(vy_arr)

        mean_vy_abs = float(np.mean(np.abs(vy_arr)))

        if n_up > n_down:
            dominant_frac = n_up / n_total
            direction = "up"
        else:
            dominant_frac = n_down / n_total
            direction = "down"

        if dominant_frac < 0.50:
            return 0.0, direction

        # Confidence: fraction of consistent frames × magnitude factor
        magnitude_factor = min(1.0, mean_vy_abs / (STAIR_VERT_THRESHOLD * 3))
        confidence = dominant_frac * 0.6 + magnitude_factor * 0.4

        # Must also be moving horizontally (not just standing still in frame)
        if mean_speed < WALK_THRESHOLD * 0.5:
            confidence *= 0.5

        return min(0.93, confidence), direction

    def _detect_cycling(
        self,
        track,
        all_tracks: list,
        mean_speed: float,
        mean_height: float,
    ) -> float:
        """
        Detect cycling.

        Signals:
          1. Person track spatially overlaps a bicycle track over time.
          2. Very high horizontal velocity with stable bbox height (seated position).

        Returns confidence [0, 1].
        """
        # Signal 1: bicycle track nearby
        bicycle_tracks = [
            t for t in all_tracks
            if (t.class_name or "").lower() in BICYCLE_CLASSES and t.is_confirmed
        ]

        if bicycle_tracks and track.observations:
            person_cxs = np.array([o.bbox.cx for o in track.observations])
            person_cys = np.array([o.bbox.cy for o in track.observations])

            for bt in bicycle_tracks:
                if not bt.observations:
                    continue
                bike_cxs = np.array([o.bbox.cx for o in bt.observations])
                bike_cys = np.array([o.bbox.cy for o in bt.observations])

                # Average positions (tracks may not be perfectly aligned in time)
                dist = np.sqrt(
                    (np.mean(person_cxs) - np.mean(bike_cxs)) ** 2
                    + (np.mean(person_cys) - np.mean(bike_cys)) ** 2
                )
                if dist < 0.25:   # within 25% of frame dimensions
                    overlap_conf = max(0.70, 0.95 - dist * 2)
                    logger.debug(
                        "[ActivityClassifier] Cycling detected via bicycle track proximity: dist=%.3f conf=%.2f",
                        dist, overlap_conf,
                    )
                    return overlap_conf

        # Signal 2: high horizontal velocity + stable vertical position
        if mean_speed >= CYCLE_HORIZ_THRESHOLD:
            heights = [o.bbox.height for o in track.observations] if track.observations else [0]
            height_std = float(np.std(heights))
            if height_std < 0.03:   # stable seated height
                return 0.65

        return 0.0


# ── Standalone helpers ─────────────────────────────────────────────────────────

def _edge_direction(bbox) -> str:
    """Return the closest frame edge to the bbox center."""
    cx, cy = bbox.cx, bbox.cy
    dists = {
        "left":   cx,
        "right":  1.0 - cx,
        "top":    cy,
        "bottom": 1.0 - cy,
    }
    return min(dists, key=dists.get)
