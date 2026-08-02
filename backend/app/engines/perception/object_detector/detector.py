"""
Object Detector Engine — Perception Engine, Phase 3B.

Runs object detection on keyframes produced by Phase 3A (scene change detection).
Operates on scene segments, not isolated frames — enabling temporal context
to be passed to downstream stages (Phase 6: Semantic Event Understanding).

Design:
- Reads keyframe_paths from context (output of s03_scene_detect).
- Loads frames with Pillow, converts to RGB numpy for model input.
- Groups detections by scene segment for temporal reasoning.
- Records per-frame and aggregate inference metrics.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.perception.object_detector.config import ObjectDetectorConfig
from app.model_registry.base_model import Detection, FrameDetectionResult
from app.model_registry.registry import ModelRegistry
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


@dataclass
class ObjectDetectionResult:
    """Complete object detection result for one video."""
    total_frames_processed: int = 0
    total_detections: int = 0
    frames_with_detections: int = 0
    frame_results: list[FrameDetectionResult] = field(default_factory=list)
    avg_inference_time_ms: float = 0.0
    model_name: str = ""
    model_version: str = ""
    confidence_threshold: float = 0.72

    def detections_by_class(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for fr in self.frame_results:
            for det in fr.detections:
                counts[det.class_name] = counts.get(det.class_name, 0) + 1
        return counts

    def to_metrics_dict(self) -> dict:
        return {
            "total_frames_processed": self.total_frames_processed,
            "total_detections": self.total_detections,
            "frames_with_detections": self.frames_with_detections,
            "detection_rate": (
                self.frames_with_detections / self.total_frames_processed
                if self.total_frames_processed > 0 else 0.0
            ),
            "avg_inference_time_ms": round(self.avg_inference_time_ms, 2),
            "model_name": self.model_name,
            "detections_by_class": self.detections_by_class(),
        }


class ObjectDetector(IntelligenceModule):
    """
    Runs object detection on keyframes using the configured model.

    Belongs to: Perception Engine
    Phase: 3B (implemented)

    The model is accessed via ModelRegistry, allowing swapping between
    YOLOv8n (current), YOLOv8s, and RT-DETR without changing this class.
    """

    name = "ObjectDetector"
    version = "0.3.1"
    engine = "Perception Engine"

    def __init__(self, config: ObjectDetectorConfig | None = None) -> None:
        self.config = config or ObjectDetectorConfig()
        self._calls_total = 0
        self._total_duration_ms = 0

    def detect_keyframes(
        self,
        keyframe_paths: list[str],
        keyframe_timestamps: dict[str, float] | None = None,
        frame_numbers: dict[str, int] | None = None,
    ) -> ObjectDetectionResult:
        """
        Run detection on a list of keyframe paths.

        Args:
            keyframe_paths:       Ordered list of JPEG paths.
            keyframe_timestamps:  Optional {path: timestamp_ms} map.
            frame_numbers:        Optional {path: frame_number} map.

        Returns:
            ObjectDetectionResult with all frame results and aggregate stats.
        """
        self._calls_total += 1
        start = time.perf_counter()

        registry = ModelRegistry.instance()
        model = registry.get(self.config.model_name)

        frame_results: list[FrameDetectionResult] = []
        total_detections = 0
        total_inference_ms = 0.0

        for path in keyframe_paths:
            frame_number = (frame_numbers or {}).get(path, 0)
            timestamp_ms = (keyframe_timestamps or {}).get(path, 0.0)

            try:
                image = _load_rgb_array(path)
            except Exception as exc:
                logger.warning("Failed to load keyframe %s: %s", path, exc)
                frame_results.append(FrameDetectionResult(
                    frame_number=frame_number,
                    frame_path=path,
                    timestamp_ms=timestamp_ms,
                    model_name=model.model_name,
                    model_version=model.model_version,
                ))
                continue

            result = model.detect(image, frame_number=frame_number, timestamp_ms=timestamp_ms)
            result.frame_path = path
            frame_results.append(result)
            total_detections += result.detection_count
            total_inference_ms += result.inference_time_ms

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._total_duration_ms += elapsed_ms

        frames_with_detections = sum(1 for r in frame_results if r.detection_count > 0)
        avg_inference = total_inference_ms / len(frame_results) if frame_results else 0.0

        return ObjectDetectionResult(
            total_frames_processed=len(keyframe_paths),
            total_detections=total_detections,
            frames_with_detections=frames_with_detections,
            frame_results=frame_results,
            avg_inference_time_ms=avg_inference,
            model_name=model.model_name,
            model_version=model.model_version,
            confidence_threshold=self.config.confidence_threshold,
        )

    async def process(self, context: PipelineContext) -> StageResult:
        """IntelligenceModule contract — delegates to s04_object_detect stage."""
        from app.pipeline.stages import s04_object_detect
        return await s04_object_detect.run(context)

    def health_check(self) -> ModuleHealth:
        try:
            registry = ModelRegistry.instance()
            model = registry.get(self.config.model_name)
            status = model.health()
            if status == "ready":
                return ModuleHealth.READY
            if status == "stub":
                return ModuleHealth.STUB
            return ModuleHealth.UNAVAILABLE
        except Exception:
            return ModuleHealth.UNAVAILABLE

    def get_metrics(self) -> ModuleMetrics:
        return ModuleMetrics(
            name=self.name,
            version=self.version,
            engine=self.engine,
            calls_total=self._calls_total,
            avg_duration_ms=(
                self._total_duration_ms / self._calls_total
                if self._calls_total > 0 else 0.0
            ),
            last_health=self.health_check(),
        )


def _load_rgb_array(path: str) -> np.ndarray:
    """Load a JPEG frame as a RGB uint8 numpy array."""
    from PIL import Image
    img = Image.open(path).convert("RGB")
    return np.asarray(img, dtype=np.uint8)
