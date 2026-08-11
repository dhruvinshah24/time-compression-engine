"""
Pose Estimation Utility — Time Compression Engine.

Uses YOLOv8-Pose to detect 17 COCO keypoints per person and derives
human activities from keypoint geometry. This is far more accurate than
bounding-box aspect ratio heuristics for detecting:

  - SITTING: hips near knee level, legs bent
  - STANDING: hips well above knees, full body height visible
  - WALKING: asymmetric ankle positions, body forward lean
  - REACHING UP: wrist above shoulder (e.g. flipping a light switch)
  - ARMS_RAISED: both wrists above shoulders

COCO Keypoint indices (17 points per person):
  0  = nose
  1  = left_eye        2  = right_eye
  3  = left_ear        4  = right_ear
  5  = left_shoulder   6  = right_shoulder
  7  = left_elbow      8  = right_elbow
  9  = left_wrist      10 = right_wrist
  11 = left_hip        12 = right_hip
  13 = left_knee       14 = right_knee
  15 = left_ankle      16 = right_ankle

All keypoint coordinates are normalized [0,1] relative to image size.
Confidence score per keypoint: 0.0 = invisible, 1.0 = high confidence.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.engines.semantic.event_understanding.rules import EventType

logger = logging.getLogger(__name__)

# ── Keypoint index constants ──────────────────────────────────────────────────
NOSE        = 0
L_EYE, R_EYE = 1, 2
L_EAR, R_EAR = 3, 4
L_SHOULDER, R_SHOULDER = 5, 6
L_ELBOW, R_ELBOW = 7, 8
L_WRIST, R_WRIST = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANKLE, R_ANKLE = 15, 16

# Minimum keypoint confidence to use a point in calculations
MIN_KP_CONF = 0.30


@dataclass
class FramePose:
    """Pose result for one person in one frame."""
    frame_number: int
    timestamp_ms: float
    # keypoints: shape (17, 3) — (x_norm, y_norm, confidence)
    keypoints: np.ndarray
    # Derived activities
    is_sitting: bool = False
    is_standing: bool = False
    is_walking: bool = False
    is_reaching_up: bool = False   # one hand above shoulder (light switch gesture)
    sit_confidence: float = 0.0
    stand_confidence: float = 0.0
    walk_confidence: float = 0.0
    reach_confidence: float = 0.0


@dataclass
class PoseEvent:
    """A semantic event derived from pose analysis."""
    event_type: str
    track_id: int
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float
    confidence: float
    evidence: dict = field(default_factory=dict)


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _avg_kp(kps: np.ndarray, *indices: int, min_conf: float = MIN_KP_CONF) -> tuple[float, float, float]:
    """
    Return the average (x, y) and mean confidence of the given keypoint indices.
    Returns (0, 0, 0) if no keypoint passes min_conf.
    """
    xs, ys, cs = [], [], []
    for i in indices:
        if i < len(kps) and kps[i, 2] >= min_conf:
            xs.append(kps[i, 0])
            ys.append(kps[i, 1])
            cs.append(kps[i, 2])
    if not xs:
        return 0.0, 0.0, 0.0
    return float(np.mean(xs)), float(np.mean(ys)), float(np.mean(cs))


def classify_pose(kps: np.ndarray) -> dict:
    """
    Classify a person's activity from 17 COCO keypoints.

    Args:
        kps: np.ndarray of shape (17, 3) — (x_norm, y_norm, confidence)

    Returns:
        dict with keys: is_sitting, is_standing, is_walking, is_reaching_up,
                         sit_conf, stand_conf, walk_conf, reach_conf, reason
    """
    result = {
        "is_sitting": False, "is_standing": False,
        "is_walking": False, "is_reaching_up": False,
        "sit_conf": 0.0, "stand_conf": 0.0,
        "walk_conf": 0.0, "reach_conf": 0.0,
        "reason": "insufficient_keypoints",
    }

    hip_x, hip_y, hip_c = _avg_kp(kps, L_HIP, R_HIP)
    knee_x, knee_y, knee_c = _avg_kp(kps, L_KNEE, R_KNEE)
    ankle_x, ankle_y, ankle_c = _avg_kp(kps, L_ANKLE, R_ANKLE)
    shoulder_x, shoulder_y, shoulder_c = _avg_kp(kps, L_SHOULDER, R_SHOULDER)
    l_wrist_x, l_wrist_y, l_wrist_c = _avg_kp(kps, L_WRIST)
    r_wrist_x, r_wrist_y, r_wrist_c = _avg_kp(kps, R_WRIST)
    l_ankle_x, l_ankle_y, l_ankle_c = _avg_kp(kps, L_ANKLE)
    r_ankle_x, r_ankle_y, r_ankle_c = _avg_kp(kps, R_ANKLE)

    # ── Sitting detection ────────────────────────────────────────────────────
    # Key insight: when sitting, the hip-to-knee vertical distance is small
    # (< 30% of shoulder-to-hip distance). When standing it's large (> 50%).
    if hip_c > MIN_KP_CONF and knee_c > MIN_KP_CONF and shoulder_c > MIN_KP_CONF:
        torso_height = abs(hip_y - shoulder_y)  # normalized
        hip_to_knee = abs(knee_y - hip_y)       # normalized

        if torso_height > 0.01:
            sit_ratio = hip_to_knee / torso_height
            # sit_ratio < 0.35 → sitting (legs bent, knees near hips)
            # sit_ratio > 0.55 → standing (legs extended)
            if sit_ratio < 0.40:
                result["is_sitting"] = True
                result["sit_conf"] = min(1.0, (0.40 - sit_ratio) / 0.40 * hip_c * knee_c)
                result["reason"] = f"sit_ratio={sit_ratio:.2f}"
            elif sit_ratio > 0.50:
                result["is_standing"] = True
                result["stand_conf"] = min(1.0, (sit_ratio - 0.50) / 0.50 * hip_c * knee_c)
                result["reason"] = f"stand_ratio={sit_ratio:.2f}"

    # ── Walking detection ────────────────────────────────────────────────────
    # When walking: left ankle x ≠ right ankle x (feet split apart laterally)
    if l_ankle_c > MIN_KP_CONF and r_ankle_c > MIN_KP_CONF:
        ankle_spread = abs(l_ankle_x - r_ankle_x)  # normalized width
        # Typical standing: spread ≈ 0.05-0.10 of frame width
        # Walking: spread ≈ 0.15-0.40 (stride)
        if ankle_spread > 0.12:
            result["is_walking"] = True
            result["walk_conf"] = min(1.0, ankle_spread * 3.0 * (l_ankle_c + r_ankle_c) / 2)
            if not result["is_sitting"]:
                result["reason"] = f"ankle_spread={ankle_spread:.2f}"

    # ── Reaching up detection ─────────────────────────────────────────────────
    # Wrist above shoulder = reaching up (flicking a light switch, pulling cord)
    if shoulder_c > MIN_KP_CONF:
        wrist_reach = False
        reach_conf = 0.0
        if l_wrist_c > MIN_KP_CONF and l_wrist_y < shoulder_y - 0.03:
            wrist_reach = True
            reach_conf = max(reach_conf, (shoulder_y - l_wrist_y) * l_wrist_c * 5.0)
        if r_wrist_c > MIN_KP_CONF and r_wrist_y < shoulder_y - 0.03:
            wrist_reach = True
            reach_conf = max(reach_conf, (shoulder_y - r_wrist_y) * r_wrist_c * 5.0)
        if wrist_reach:
            result["is_reaching_up"] = True
            result["reach_conf"] = min(1.0, reach_conf)
            result["reason"] = result.get("reason", "") + " + reaching_up"

    return result


# ── Frame-level pose analysis ─────────────────────────────────────────────────

def analyze_pose_frames(
    frame_paths: list[str],
    frame_numbers: list[int],
    timestamps_ms: list[float],
    model_name: str = "yolov8n-pose",
    confidence: float = 0.20,
) -> list[FramePose]:
    """
    Run pose estimation on a list of frame images.

    Args:
        frame_paths:   Absolute paths to JPEG frames.
        frame_numbers: Corresponding frame numbers.
        timestamps_ms: Corresponding timestamps.
        model_name:    Pose model name (auto-downloads if not cached).
        confidence:    Detection confidence threshold.

    Returns:
        List of FramePose objects, one per person detected per frame.
        May be empty if no people found.
    """
    results: list[FramePose] = []

    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        logger.warning("ultralytics not installed — pose analysis skipped")
        return results

    try:
        model = YOLO(f"{model_name}.pt")
        logger.info("Loaded pose model: %s", model_name)
    except Exception as exc:
        logger.warning("Failed to load pose model %s: %s — skipping", model_name, exc)
        return results

    for path, frame_num, ts_ms in zip(frame_paths, frame_numbers, timestamps_ms):
        try:
            preds = model(path, conf=confidence, verbose=False)
        except Exception as exc:
            logger.warning("Pose inference failed for frame %d: %s", frame_num, exc)
            continue

        for pred in preds:
            if pred.keypoints is None:
                continue
            kps_data = pred.keypoints.data  # shape (N_persons, 17, 3)
            if kps_data is None or len(kps_data) == 0:
                continue
            for person_kps in kps_data:
                kps_np = person_kps.cpu().numpy()  # (17, 3)
                classification = classify_pose(kps_np)
                fp = FramePose(
                    frame_number=frame_num,
                    timestamp_ms=ts_ms,
                    keypoints=kps_np,
                    is_sitting=classification["is_sitting"],
                    is_standing=classification["is_standing"],
                    is_walking=classification["is_walking"],
                    is_reaching_up=classification["is_reaching_up"],
                    sit_confidence=classification["sit_conf"],
                    stand_confidence=classification["stand_conf"],
                    walk_confidence=classification["walk_conf"],
                    reach_confidence=classification["reach_conf"],
                )
                results.append(fp)

    return results


# ── Event extraction from pose sequence ──────────────────────────────────────

def extract_pose_events(
    frame_poses: list[FramePose],
    track_id: int = -1,
    min_consecutive_frames: int = 2,
    fps: float = 30.0,
) -> list[PoseEvent]:
    """
    Extract semantic events from a temporal sequence of pose frames.

    Groups consecutive frames with the same activity and emits events
    only when the activity persists for min_consecutive_frames.

    Args:
        frame_poses:            Ordered FramePose objects for ONE person track.
        track_id:               Track ID to stamp on events.
        min_consecutive_frames: Minimum frames to confirm an activity.
        fps:                    Video FPS (for min duration filter).

    Returns:
        List of PoseEvent objects in chronological order.
    """
    if not frame_poses:
        return []

    events: list[PoseEvent] = []
    sorted_poses = sorted(frame_poses, key=lambda p: p.frame_number)

    # State machine: track current confirmed activity
    current_activity: str | None = None
    activity_start_frame: int = sorted_poses[0].frame_number
    activity_start_ms: float = sorted_poses[0].timestamp_ms
    streak_count: int = 0

    # Previous state for transition detection
    prev_was_sitting = False
    last_reaching_frame: int = -999
    last_reaching_ms: float = 0.0

    for pose in sorted_poses:
        # Determine dominant activity for this frame
        activities = []
        if pose.is_sitting and pose.sit_confidence > 0.3:
            activities.append(("sitting", pose.sit_confidence))
        elif pose.is_standing and pose.stand_confidence > 0.3:
            activities.append(("standing", pose.stand_confidence))
        if pose.is_walking and pose.walk_confidence > 0.3:
            activities.append(("walking", pose.walk_confidence))

        dominant = max(activities, key=lambda x: x[1])[0] if activities else None

        # Reaching up: emit immediately (it's a momentary gesture)
        if pose.is_reaching_up and pose.reach_confidence > 0.4:
            gap = pose.frame_number - last_reaching_frame
            if gap > 20:  # debounce — don't re-emit within 20 frames
                events.append(PoseEvent(
                    event_type=EventType.PERSON_REACHING_UP,
                    track_id=track_id,
                    start_frame=pose.frame_number,
                    end_frame=pose.frame_number,
                    start_ms=pose.timestamp_ms,
                    end_ms=pose.timestamp_ms,
                    confidence=pose.reach_confidence,
                    evidence={
                        "reach_conf": round(pose.reach_confidence, 3),
                        "frame": pose.frame_number,
                        "timestamp_s": round(pose.timestamp_ms / 1000, 2),
                        "source": "pose_keypoints",
                    },
                ))
                last_reaching_frame = pose.frame_number
                last_reaching_ms = pose.timestamp_ms

        if dominant == current_activity:
            streak_count += 1
        else:
            # Emit event for ended activity if long enough
            if current_activity is not None and streak_count >= min_consecutive_frames:
                evt_type = _activity_to_event_type(
                    current_activity,
                    prev_was_sitting=(current_activity == "standing" and prev_was_sitting),
                )
                if evt_type:
                    events.append(PoseEvent(
                        event_type=evt_type,
                        track_id=track_id,
                        start_frame=activity_start_frame,
                        end_frame=pose.frame_number,
                        start_ms=activity_start_ms,
                        end_ms=pose.timestamp_ms,
                        confidence=_activity_confidence(sorted_poses, activity_start_frame, pose.frame_number, current_activity),
                        evidence={
                            "activity": current_activity,
                            "frames": streak_count,
                            "duration_s": round((pose.timestamp_ms - activity_start_ms) / 1000, 2),
                            "source": "pose_keypoints",
                        },
                    ))
                if current_activity == "sitting":
                    prev_was_sitting = True
            # Reset
            current_activity = dominant
            activity_start_frame = pose.frame_number
            activity_start_ms = pose.timestamp_ms
            streak_count = 1

    # Emit final activity
    if current_activity is not None and streak_count >= min_consecutive_frames:
        evt_type = _activity_to_event_type(
            current_activity,
            prev_was_sitting=(current_activity == "standing" and prev_was_sitting),
        )
        if evt_type:
            last_pose = sorted_poses[-1]
            events.append(PoseEvent(
                event_type=evt_type,
                track_id=track_id,
                start_frame=activity_start_frame,
                end_frame=last_pose.frame_number,
                start_ms=activity_start_ms,
                end_ms=last_pose.timestamp_ms,
                confidence=_activity_confidence(sorted_poses, activity_start_frame, last_pose.frame_number, current_activity),
                evidence={
                    "activity": current_activity,
                    "frames": streak_count,
                    "duration_s": round((last_pose.timestamp_ms - activity_start_ms) / 1000, 2),
                    "source": "pose_keypoints",
                },
            ))

    return events


def _activity_to_event_type(activity: str, prev_was_sitting: bool = False) -> str | None:
    """Map activity name to EventType constant."""
    if activity == "sitting":
        return EventType.PERSON_SITTING
    if activity == "standing":
        # If we're transitioning from sitting → standing, it's "stood up"
        return EventType.PERSON_STANDING_UP if prev_was_sitting else EventType.PERSON_STANDING
    if activity == "walking":
        return EventType.PERSON_WALKING
    return None


def _activity_confidence(poses: list[FramePose], start_f: int, end_f: int, activity: str) -> float:
    """Compute mean confidence for an activity over a range of frames."""
    relevant = [p for p in poses if start_f <= p.frame_number <= end_f]
    if not relevant:
        return 0.5
    attr_map = {
        "sitting": "sit_confidence",
        "standing": "stand_confidence",
        "walking": "walk_confidence",
    }
    attr = attr_map.get(activity)
    if not attr:
        return 0.5
    vals = [getattr(p, attr) for p in relevant if getattr(p, attr) > 0]
    return float(np.mean(vals)) if vals else 0.5
