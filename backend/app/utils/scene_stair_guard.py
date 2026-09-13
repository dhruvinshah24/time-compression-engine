"""
Scene Stair Guard — Phase 6E.13 Integration.

Provides scene-context verification for velocity-derived stair walking events,
integrating the exact evidence chain validated in Phase 6E.11 and Phase 6E.12.

Conceptual Pipeline:
    Person detection
        ↓
    Track (MultiObjectTracker)
        ↓
    Automatic 1.5x Person ROI
        ↓
    Expanded Stair Scene Vocabulary (YOLO-World)
        ↓
    Scene Stair Confidence (c_scene)
        ↓
    Temporal Persistence (p_scene >= 2)
        ↓
    Spatial Relation / IoP (iop >= 0.15)
        ↓
    Locomotion Evidence (c_vel)
        ↓
    QualityScore & Soft Evidence Fusion:
        quality = min(1.0, (c_scene / 0.05) * (p_scene / 5.0) * min(1.0, iop / 0.20))
        c_stair = c_vel * (0.30 + 0.70 * quality)
        threshold = 0.55
        ↓
    Explainable Verification Decision:
        - Verified stair climbing if c_stair >= 0.55
        - Clean fallback to flat-ground walking/running if suppressed
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Frozen Hyperparameters from Phase 6E.11 & 6E.12
EXPANDED_STAIR_VOCABULARY = [
    "stairs", "staircase", "steps", "stairway", "flight of stairs",
    "stair steps", "staircase steps", "stairwell", "stone steps",
    "concrete stairs", "indoor stairs", "outdoor stairs",
]

TAU_REF = 0.05
P_REF = 5.0
IOP_REF = 0.20
W_BASE = 0.30
MIN_PERSISTENCE = 2
MIN_IOP = 0.15
DEFAULT_STAIR_THRESH = 0.55
PERSON_ROI_SCALE = 1.5


@dataclass
class StairGuardEvidence:
    """Explainability record for stair classification under the scene guard."""
    velocity_confidence: float
    scene_stair_confidence: float
    scene_stair_persistence: int
    spatial_relation_iop: float
    quality_score: float
    final_stair_confidence: float
    is_verified: bool
    fallback_activity_label: Optional[str] = None
    decision_path: str = "scene_stair_guard"
    feature_flag_state: bool = True
    inferences_count: int = 0
    inference_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "velocity_confidence": round(self.velocity_confidence, 4),
            "scene_stair_confidence": round(self.scene_stair_confidence, 4),
            "scene_stair_persistence": self.scene_stair_persistence,
            "spatial_relation_iop": round(self.spatial_relation_iop, 4),
            "quality_score": round(self.quality_score, 4),
            "final_stair_confidence": round(self.final_stair_confidence, 4),
            "is_verified": self.is_verified,
            "fallback_activity_label": self.fallback_activity_label,
            "decision_path": self.decision_path,
            "feature_flag_state": self.feature_flag_state,
            "inferences_count": self.inferences_count,
            "inference_duration_ms": round(self.inference_duration_ms, 2),
        }


def compute_iop(person_bbox: list[float], stair_bbox: list[float]) -> float:
    """
    Compute Intersection-over-Person (IoP).
    person_bbox, stair_bbox are in normalized coordinates [x1, y1, x2, y2].
    """
    px1, py1, px2, py2 = person_bbox
    sx1, sy1, sx2, sy2 = stair_bbox

    ix1 = max(px1, sx1)
    iy1 = max(py1, sy1)
    ix2 = min(px2, sx2)
    iy2 = min(py2, sy2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter_area = iw * ih

    person_area = max(1e-6, (px2 - px1) * (py2 - py1))
    return inter_area / person_area


def expand_person_roi(
    bbox: list[float],
    frame_w: int,
    frame_h: int,
    scale: float = PERSON_ROI_SCALE,
) -> tuple[int, int, int, int]:
    """
    Calculate 1.5x spatial expansion around person bounding box in pixel coordinates.
    Returns: (rx1, ry1, rx2, ry2) clamped to image boundary.
    """
    x1, y1, x2, y2 = bbox
    # If normalized, convert to pixel coordinates
    if any(v <= 1.5 for v in [x1, y1, x2, y2]):
        px1, py1 = x1 * frame_w, y1 * frame_h
        px2, py2 = x2 * frame_w, y2 * frame_h
    else:
        px1, py1, px2, py2 = x1, y1, x2, y2

    pw = max(1.0, px2 - px1)
    ph = max(1.0, py2 - py1)

    pad_x = (pw * (scale - 1.0)) / 2.0
    pad_y = (ph * (scale - 1.0)) / 2.0

    rx1 = max(0, int(px1 - pad_x))
    ry1 = max(0, int(py1 - pad_y))
    rx2 = min(frame_w, int(px2 + pad_x))
    ry2 = min(frame_h, int(py2 + pad_y))

    return rx1, ry1, rx2, ry2


class SceneStairGuard:
    """
    Evaluates staircase scene context for candidate stair climbing tracks.
    """

    def __init__(self, weights_path: Optional[str | Path] = None) -> None:
        if weights_path:
            self.weights_path = Path(weights_path)
        else:
            candidates = [
                Path(__file__).resolve().parents[2] / "yolov8l-worldv2.pt",
                Path(__file__).resolve().parents[1] / "yolov8l-worldv2.pt",
                Path("yolov8l-worldv2.pt"),
                Path("backend/yolov8l-worldv2.pt"),
            ]
            self.weights_path = next((p for p in candidates if p.exists()), candidates[0])
        self._model = None

    def _get_model(self):
        if self._model is None:
            if not self.weights_path.exists():
                logger.warning("YOLO-World weights not found at %s", self.weights_path)
                return None
            try:
                from ultralytics import YOLO
                model = YOLO(str(self.weights_path))
                model.set_classes(EXPANDED_STAIR_VOCABULARY)
                self._model = model
            except Exception as e:
                logger.error("Failed to load YOLO-World for SceneStairGuard: %s", e)
                return None
        return self._model

    def evaluate_track_stair_context(
        self,
        track,
        frame_paths_map: dict[int, str],
        frame_w: int,
        frame_h: int,
        c_vel: float,
        stair_dir: str,
        mean_speed: float = 0.015,
    ) -> StairGuardEvidence:
        """
        Evaluate scene evidence for a track that exhibited stair vertical velocity.
        """
        import time
        t_start = time.perf_counter()

        model = self._get_model()
        if model is None:
            # Fallback if model weights unavailable: conservative rejection
            from app.utils.activity_classifier import RUN_THRESHOLD
            fallback = "running" if mean_speed >= RUN_THRESHOLD else "walking"
            return StairGuardEvidence(
                velocity_confidence=c_vel,
                scene_stair_confidence=0.0,
                scene_stair_persistence=0,
                spatial_relation_iop=0.0,
                quality_score=0.0,
                final_stair_confidence=round(c_vel * W_BASE, 4),
                is_verified=False,
                fallback_activity_label=fallback,
                decision_path="scene_guard_weights_unavailable",
                feature_flag_state=True,
            )

        obs = track.observations
        if not obs:
            return StairGuardEvidence(
                velocity_confidence=c_vel,
                scene_stair_confidence=0.0,
                scene_stair_persistence=0,
                spatial_relation_iop=0.0,
                quality_score=0.0,
                final_stair_confidence=0.0,
                is_verified=False,
                fallback_activity_label="walking",
                decision_path="no_observations",
                feature_flag_state=True,
            )

        # Inspect up to 10 temporally distributed observations
        sample_step = max(1, len(obs) // 10)
        sampled_obs = obs[::sample_step]

        frames_with_stair = 0
        max_scene_conf = 0.0
        max_iop = 0.0
        inferences_run = 0

        for o in sampled_obs:
            fn = o.frame_number
            fpath = frame_paths_map.get(fn)
            if not fpath or not Path(fpath).exists():
                continue

            frame_img = cv2.imread(fpath)
            if frame_img is None:
                continue

            # Person bbox in normalized coordinates
            b = o.bbox
            from app.engines.perception.tracker.track import TrackBBox
            if isinstance(b, TrackBBox):
                bx1, by1, bx2, by2 = b.x1, b.y1, b.x2, b.y2
            elif hasattr(b, "__len__") and len(b) >= 4:
                bx1, by1, bx2, by2 = b[0], b[1], b[2], b[3]
            else:
                continue

            if any(v > 1.5 for v in [bx1, by1, bx2, by2]):
                p_norm = [bx1 / max(frame_w, 1), by1 / max(frame_h, 1),
                          bx2 / max(frame_w, 1), by2 / max(frame_h, 1)]
            else:
                p_norm = [bx1, by1, bx2, by2]

            # Automatic 1.5x Person ROI
            rx1, ry1, rx2, ry2 = expand_person_roi(p_norm, frame_w, frame_h, scale=PERSON_ROI_SCALE)
            roi_crop = frame_img[ry1:ry2, rx1:rx2]

            if roi_crop.shape[0] < 20 or roi_crop.shape[1] < 20:
                continue

            inferences_run += 1
            results = model.predict(roi_crop, conf=0.01, verbose=False)
            frame_stair_detected = False

            for r in results:
                if r.boxes is not None and len(r.boxes) > 0:
                    for box in r.boxes:
                        conf = float(box.conf[0].item())
                        c_xyxy = box.xyxy[0].tolist()

                        # Convert crop coords back to full-frame normalized coords
                        stair_norm = [
                            (rx1 + c_xyxy[0]) / max(frame_w, 1),
                            (ry1 + c_xyxy[1]) / max(frame_h, 1),
                            (rx1 + c_xyxy[2]) / max(frame_w, 1),
                            (ry1 + c_xyxy[3]) / max(frame_h, 1),
                        ]

                        iop = compute_iop(p_norm, stair_norm)
                        if conf > max_scene_conf:
                            max_scene_conf = conf
                        if iop > max_iop:
                            max_iop = iop

                        if conf >= 0.02 and iop >= MIN_IOP:
                            frame_stair_detected = True

            if frame_stair_detected:
                frames_with_stair += 1

        duration_ms = (time.perf_counter() - t_start) * 1000.0

        # Calculate QualityScore and Final Fused Stair Confidence
        if frames_with_stair >= MIN_PERSISTENCE and max_iop >= MIN_IOP:
            norm_cs = max_scene_conf / TAU_REF
            norm_ps = frames_with_stair / P_REF
            norm_iop = min(1.0, max_iop / IOP_REF)
            quality_score = min(1.0, norm_cs * norm_ps * norm_iop)
        else:
            quality_score = 0.0

        factor = W_BASE + (1.0 - W_BASE) * quality_score
        final_stair_conf = c_vel * factor
        is_verified = (final_stair_conf >= DEFAULT_STAIR_THRESH)

        fallback_label = None
        if not is_verified:
            from app.utils.activity_classifier import RUN_THRESHOLD
            fallback_label = "running" if mean_speed >= RUN_THRESHOLD else "walking"

        return StairGuardEvidence(
            velocity_confidence=c_vel,
            scene_stair_confidence=max_scene_conf,
            scene_stair_persistence=frames_with_stair,
            spatial_relation_iop=max_iop,
            quality_score=quality_score,
            final_stair_confidence=final_stair_conf,
            is_verified=is_verified,
            fallback_activity_label=fallback_label,
            decision_path="automatic_person_roi_scene_guard",
            feature_flag_state=True,
            inferences_count=inferences_run,
            inference_duration_ms=duration_ms,
        )