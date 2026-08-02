"""Stub detection model — returns empty detections. Used in tests and when YOLO is not installed."""

import time
import numpy as np
from app.model_registry.base_model import BaseDetectionModel, Detection, FrameDetectionResult


class StubDetectionModel(BaseDetectionModel):
    """
    Stub model for testing and graceful degradation.

    Returns empty FrameDetectionResult without running any inference.
    The pipeline continues normally — downstream stages receive zero detections.

    This is intentional: the pipeline should be fully exercisable
    without any AI models installed, using stub outputs.
    """

    def detect(
        self,
        image: np.ndarray,
        frame_number: int = 0,
        timestamp_ms: float = 0.0,
    ) -> FrameDetectionResult:
        self._calls_total += 1
        return FrameDetectionResult(
            frame_number=frame_number,
            frame_path="",
            timestamp_ms=timestamp_ms,
            detections=[],
            inference_time_ms=0.0,
            model_name=self.model_name,
            model_version=self.model_version,
        )

    def health(self) -> str:
        return "stub"
