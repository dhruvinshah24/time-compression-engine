"""
YOLO Detection Model — wraps ultralytics YOLOv8 behind the BaseDetectionModel interface.

Algorithm selection rationale (Phase 3B):
  Problem:    Detect objects (person, vehicle, parcel) in video keyframes.
  Chosen:     YOLOv8n (Nano) — fastest variant for baseline.
  Why YOLO:   Single-pass detection (not two-stage like Faster R-CNN).
              Real-time capable on CPU and GPU.
              Well-documented, reproducible, actively maintained.
  Why Nano:   The goal in Phase 3B is reliable inference, not highest accuracy.
              Accuracy optimization (YOLOv8s, YOLOv8m, RT-DETR) is Phase 9.

COCO class mapping:
  Only a subset of YOLO's 80 COCO classes are relevant to this system.
  Relevant IDs: 0=person, 1=bicycle, 2=car, 3=motorcycle, 5=bus, 7=truck,
                24=backpack, 26=handbag, 28=suitcase, 67=cell phone.
  All other classes are filtered based on system_settings.

Output normalization:
  YOLO returns pixel coordinates. We normalize to [0,1] and store both
  for downstream convenience (normalized for comparison, pixels for display).

Error handling:
  - ultralytics not installed → health() returns "unavailable", detect() raises ImportError.
  - Model weights not found → health() returns "unavailable".
  - Inference error → logs warning, returns empty FrameDetectionResult (non-fatal).
"""

from __future__ import annotations

import logging
import time

import numpy as np

from app.model_registry.base_model import BaseDetectionModel, Detection, FrameDetectionResult

logger = logging.getLogger(__name__)

# COCO class IDs that are relevant to surveillance/event detection
# Full COCO list: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml
RELEVANT_COCO_CLASSES: set[int] = {
    0,   # person
    1,   # bicycle
    2,   # car
    3,   # motorcycle
    5,   # bus
    7,   # truck
    24,  # backpack
    26,  # handbag
    28,  # suitcase
    67,  # cell phone
}


class YOLODetectionModel(BaseDetectionModel):
    """
    YOLOv8 object detector.

    Lazy loads the ultralytics YOLO model on first call to detect().
    This avoids blocking app startup if the model isn't immediately needed.
    """

    def __init__(self, spec) -> None:
        super().__init__(spec)
        self._model = None
        self._ultralytics_available: bool | None = None
        self._load_error: str | None = None

    def _ensure_loaded(self) -> bool:
        """Lazy-load the YOLO model. Returns True if successfully loaded."""
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False

        try:
            from ultralytics import YOLO  # type: ignore
            weight = self.spec.weight_path or f"{self.spec.name}.pt"
            logger.info("Loading YOLO model: %s (weights=%s)", self.spec.name, weight)
            self._model = YOLO(weight)
            self._ultralytics_available = True
            logger.info("YOLO model loaded: %s", self.spec.name)
            return True
        except ImportError:
            self._load_error = (
                "ultralytics not installed. "
                "Run: pip install ultralytics"
            )
            self._ultralytics_available = False
            logger.warning(self._load_error)
            return False
        except Exception as exc:
            self._load_error = str(exc)
            logger.warning("Failed to load YOLO model %s: %s", self.spec.name, exc)
            return False

    def detect(
        self,
        image: np.ndarray,
        frame_number: int = 0,
        timestamp_ms: float = 0.0,
    ) -> FrameDetectionResult:
        """
        Run YOLOv8 inference on a single frame.

        Args:
            image:        RGB uint8 numpy array (H, W, 3).
            frame_number: Frame number for provenance.
            timestamp_ms: Timestamp for event correlation.

        Returns:
            FrameDetectionResult. Empty detections if model unavailable (non-fatal).

        Raises:
            ImportError: If ultralytics is not installed (for early-fail in tests).
        """
        self._calls_total += 1
        start = time.perf_counter()

        if not self._ensure_loaded():
            if self._ultralytics_available is False:
                raise ImportError(self._load_error or "ultralytics not available")
            return FrameDetectionResult(
                frame_number=frame_number,
                frame_path="",
                timestamp_ms=timestamp_ms,
                model_name=self.model_name,
                model_version=self.model_version,
            )

        img_h, img_w = image.shape[:2]
        detections: list[Detection] = []
        pre_confidence_filter_count = 0  # boxes YOLO returned before our confidence filter

        try:
            results = self._model(
                image,
                conf=self.spec.confidence_threshold,
                verbose=False,
            )

            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                pre_confidence_filter_count += len(boxes)  # track raw post-NMS count

                for i in range(len(boxes)):
                    class_id = int(boxes.cls[i].item())
                    if self.spec.classes is None and class_id not in RELEVANT_COCO_CLASSES:
                        continue

                    confidence = float(boxes.conf[i].item())
                    if confidence < self.spec.confidence_threshold:
                        continue

                    # Pixel coordinates (xyxy format)
                    x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

                    # Normalize to [0, 1]
                    nx1 = x1 / img_w
                    ny1 = y1 / img_h
                    nx2 = x2 / img_w
                    ny2 = y2 / img_h

                    class_name = result.names.get(class_id, str(class_id))

                    detections.append(Detection(
                        class_id=class_id,
                        class_name=class_name,
                        confidence=confidence,
                        bbox_x1=nx1,
                        bbox_y1=ny1,
                        bbox_x2=nx2,
                        bbox_y2=ny2,
                        bbox_px_x1=x1,
                        bbox_px_y1=y1,
                        bbox_px_x2=x2,
                        bbox_px_y2=y2,
                        frame_number=frame_number,
                        timestamp_ms=timestamp_ms,
                        model_name=self.model_name,
                        model_version=self.model_version,
                    ))

        except Exception as exc:
            logger.warning(
                "YOLO inference failed for frame %d: %s (returning empty result)",
                frame_number, exc
            )

        inference_ms = (time.perf_counter() - start) * 1000
        self._total_inference_ms += inference_ms

        for det in detections:
            det.inference_time_ms = inference_ms

        return FrameDetectionResult(
            frame_number=frame_number,
            frame_path="",
            timestamp_ms=timestamp_ms,
            detections=detections,
            inference_time_ms=inference_ms,
            model_name=self.model_name,
            model_version=self.model_version,
            weights_path=self.spec.weight_path or f"{self.spec.name}.pt",
            confidence_threshold=self.spec.confidence_threshold,
            pre_confidence_filter_count=pre_confidence_filter_count,
        )

    def health(self) -> str:
        if self._model is not None:
            return "ready"
        if self._load_error:
            return "unavailable"
        # Not yet loaded — try a quick check
        try:
            import ultralytics  # noqa: F401
            return "ready"
        except ImportError:
            return "unavailable"
