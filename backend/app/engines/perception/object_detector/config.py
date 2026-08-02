"""Configuration for the Object Detector module."""
from dataclasses import dataclass


@dataclass
class ObjectDetectorConfig:
    """
    Configuration for Phase 3B Object Detection.

    model_name:           Model to use from the registry (default: "yolov8n").
                          Override via system_settings key "detection_model_name".
    confidence_threshold: Minimum score to accept a detection [0, 1].
                          Override via system_settings key "detection_confidence".
    batch_size:           Frames to process per inference call. 1 = per-frame.
                          Larger batches improve GPU utilization.

    Phase 3B note:
    - Start with yolov8n (nano). Smallest, fastest, lowest accuracy.
    - Upgrade to yolov8s in Phase 9 after evaluation metrics are established.
    """
    model_name: str = "yolov8n"
    confidence_threshold: float = 0.72
    batch_size: int = 1
