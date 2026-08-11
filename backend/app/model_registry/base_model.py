"""
Base class for all detection models in the model registry.

Every backend (YOLO, DINO, RT-DETR) implements this interface.
The pipeline never touches framework-specific APIs directly —
it only calls detect() and gets back a list of Detection objects.

This is the key abstraction that makes model swapping possible.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from app.model_registry.registry import ModelSpec


@dataclass
class Detection:
    """
    A single object detection result.

    All coordinates are normalized to [0.0, 1.0] relative to image dimensions.
    Pixel coordinates are also provided for display and ROI cropping.

    Normalization rationale:
    - Normalized coordinates are resolution-independent.
    - Enables direct comparison between detections from different image sizes.
    - Pixel coordinates are derived from normalized + image size.
    """
    # Classification
    class_id: int
    class_name: str
    confidence: float              # [0.0, 1.0]

    # Bounding box — normalized [0.0, 1.0] (x1, y1, x2, y2 format)
    bbox_x1: float
    bbox_y1: float
    bbox_x2: float
    bbox_y2: float

    # Bounding box — pixel coordinates (convenience)
    bbox_px_x1: int = 0
    bbox_px_y1: int = 0
    bbox_px_x2: int = 0
    bbox_px_y2: int = 0

    # Context
    frame_number: int = 0
    timestamp_ms: float = 0.0

    # Model provenance (important for research — which model produced this?)
    model_name: str = ""
    model_version: str = ""
    inference_time_ms: float = 0.0

    @property
    def center_x(self) -> float:
        return (self.bbox_x1 + self.bbox_x2) / 2

    @property
    def center_y(self) -> float:
        return (self.bbox_y1 + self.bbox_y2) / 2

    @property
    def width(self) -> float:
        return self.bbox_x2 - self.bbox_x1

    @property
    def height(self) -> float:
        return self.bbox_y2 - self.bbox_y1

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_dict(self) -> dict:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 4),
            "bbox_normalized": [self.bbox_x1, self.bbox_y1, self.bbox_x2, self.bbox_y2],
            "bbox_pixels": [self.bbox_px_x1, self.bbox_px_y1, self.bbox_px_x2, self.bbox_px_y2],
            "frame_number": self.frame_number,
            "timestamp_ms": self.timestamp_ms,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "inference_time_ms": self.inference_time_ms,
        }


@dataclass
class FrameDetectionResult:
    """
    All detections for a single frame, with full model provenance.

    Provenance fields make experiments reproducible: you can always trace
    which model, version, and threshold produced a specific detection.

    NMS metrics:
    - pre_confidence_filter_count: raw boxes from YOLO before confidence filter.
      Note: YOLO internally applies NMS before returning results. This field
      captures how many boxes survived YOLO's NMS but were then filtered by our
      confidence_threshold. It is NOT the pre-NMS count (YOLO doesn't expose that
      via the standard API). Documented accurately to avoid misleading claims.
    - detection_count (property): final accepted detections.
    """
    frame_number: int
    frame_path: str
    timestamp_ms: float
    detections: list[Detection] = field(default_factory=list)
    inference_time_ms: float = 0.0
    model_name: str = ""
    model_version: str = ""
    # Model provenance — for experiment reproducibility
    weights_path: str = ""            # e.g. "yolov8n.pt" or absolute path
    confidence_threshold: float = 0.0  # threshold used for this inference
    # NMS metrics
    pre_confidence_filter_count: int = 0  # boxes from YOLO before our threshold filter

    @property
    def detection_count(self) -> int:
        return len(self.detections)

    @property
    def filtered_out_count(self) -> int:
        """Boxes that YOLO returned but we rejected below our confidence threshold."""
        return max(0, self.pre_confidence_filter_count - self.detection_count)

    def to_dict(self) -> dict:
        return {
            "frame_number": self.frame_number,
            "timestamp_ms": self.timestamp_ms,
            "detection_count": self.detection_count,
            "inference_time_ms": self.inference_time_ms,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "weights_path": self.weights_path,
            "confidence_threshold": self.confidence_threshold,
            "pre_confidence_filter_count": self.pre_confidence_filter_count,
            "filtered_out_count": self.filtered_out_count,
            "detections": [d.to_dict() for d in self.detections],
        }



class BaseDetectionModel(ABC):
    """
    Abstract base class for all detection model backends.

    All backends must implement:
    - detect(image, frame_number, timestamp_ms) → FrameDetectionResult
    - health() → str (one of: "ready", "stub", "unavailable")
    - model_name → str
    - model_version → str
    """

    def __init__(self, spec: ModelSpec) -> None:
        self.spec = spec
        self._calls_total = 0
        self._total_inference_ms = 0.0

    @property
    def model_name(self) -> str:
        return self.spec.name

    @property
    def model_version(self) -> str:
        return self.spec.version

    @property
    def confidence_threshold(self) -> float:
        return self.spec.confidence_threshold

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        frame_number: int = 0,
        timestamp_ms: float = 0.0,
        override_confidence: float | None = None,
    ) -> FrameDetectionResult:
        """
        Run inference on a single frame.

        Args:
            image:               RGB uint8 numpy array (H, W, 3).
            frame_number:        Original frame number for provenance.
            timestamp_ms:        Frame timestamp for event correlation.
            override_confidence: If set, use this instead of spec default.

        Returns:
            FrameDetectionResult with all detections above confidence_threshold.
        """

    @abstractmethod
    def health(self) -> str:
        """Return model health status: "ready", "stub", or "unavailable"."""

    def get_performance_stats(self) -> dict:
        """Return call count and average inference time."""
        return {
            "calls_total": self._calls_total,
            "avg_inference_ms": (
                self._total_inference_ms / self._calls_total
                if self._calls_total > 0 else 0.0
            ),
        }
