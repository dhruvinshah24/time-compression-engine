"""
Model Registry — Time Compression Engine.

Central registry for all AI models used in the Perception Engine.
Supports multiple model backends (YOLO, DINO, RT-DETR) behind a common
interface, enabling model switching and A/B comparison via system_settings.

Design principles:
- No model is loaded until explicitly requested (lazy loading).
- Every model wraps its output into the same normalized Detection format.
- Version and inference timing are always recorded.
- Stubs return empty detections with ModuleHealth.STUB — the pipeline
  continues without crashing when a model is not yet installed.

Phase 3B: YOLOv8 stub → real YOLOv8n integration.
Phase 9+:  Swap to YOLOv8s or RT-DETR for accuracy benchmarks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.model_registry.base_model import BaseDetectionModel

logger = logging.getLogger(__name__)


class ModelBackend(str, Enum):
    YOLO = "yolo"
    DINO = "dino"
    RTDETR = "rtdetr"
    STUB = "stub"


@dataclass
class ModelSpec:
    """
    Specification for a registered detection model.

    name:         Unique identifier (e.g., "yolov8n", "yolov8s")
    backend:      Which framework powers this model
    version:      Model version string (for logging + metrics)
    weight_path:  Path to model weights file. If None, ultralytics auto-downloads.
    input_size:   Expected input image size (width, height)
    confidence_threshold:  Minimum detection confidence to include
    classes:      List of class names this model outputs. None = use model defaults.
    description:  Human-readable description for the model registry API.
    """
    name: str
    backend: ModelBackend
    version: str
    weight_path: str | None = None
    input_size: tuple[int, int] = (640, 640)
    confidence_threshold: float = 0.72
    classes: list[str] | None = None
    description: str = ""


# ---------------------------------------------------------------------------
# Built-in model specs
# ---------------------------------------------------------------------------

YOLOV8N_SPEC = ModelSpec(
    name="yolov8n",
    backend=ModelBackend.YOLO,
    version="8.0.0",
    weight_path=None,  # Auto-download from ultralytics
    input_size=(640, 640),
    confidence_threshold=0.72,
    description="YOLOv8 Nano — fastest, lowest accuracy. Good for Phase 3B baseline.",
)

YOLOV8S_SPEC = ModelSpec(
    name="yolov8s",
    backend=ModelBackend.YOLO,
    version="8.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.72,
    description="YOLOv8 Small — Phase 9 accuracy upgrade candidate.",
)

STUB_SPEC = ModelSpec(
    name="stub",
    backend=ModelBackend.STUB,
    version="0.0.0",
    description="Stub model — returns empty detections. Used when no model is installed.",
)

_BUILTIN_SPECS: dict[str, ModelSpec] = {
    "yolov8n": YOLOV8N_SPEC,
    "yolov8s": YOLOV8S_SPEC,
    "stub": STUB_SPEC,
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """
    Singleton registry for all detection models.

    Usage:
        registry = ModelRegistry.instance()
        model = registry.get("yolov8n")
        detections = model.detect(frame_array)
    """

    _instance: ModelRegistry | None = None

    def __init__(self) -> None:
        self._specs: dict[str, ModelSpec] = dict(_BUILTIN_SPECS)
        self._loaded: dict[str, BaseDetectionModel] = {}

    @classmethod
    def instance(cls) -> ModelRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton — for testing only."""
        cls._instance = None

    def register(self, spec: ModelSpec) -> None:
        """Register a new model spec (or override an existing one)."""
        self._specs[spec.name] = spec
        logger.info("Registered model: %s (%s v%s)", spec.name, spec.backend, spec.version)

    def get_spec(self, name: str) -> ModelSpec | None:
        """Return the ModelSpec for a registered model name."""
        return self._specs.get(name)

    def list_models(self) -> list[ModelSpec]:
        """Return all registered model specs."""
        return list(self._specs.values())

    def get(self, name: str) -> BaseDetectionModel:
        """
        Return a loaded model instance, loading it lazily on first access.

        Args:
            name: Registered model name (e.g., "yolov8n", "stub")

        Returns:
            BaseDetectionModel instance.

        Raises:
            KeyError: If the model name is not registered.
        """
        if name not in self._specs:
            raise KeyError(
                f"Model '{name}' not registered. "
                f"Available: {list(self._specs.keys())}"
            )

        if name not in self._loaded:
            self._loaded[name] = self._load(name)

        return self._loaded[name]

    def unload(self, name: str) -> None:
        """Unload a model to free memory."""
        if name in self._loaded:
            del self._loaded[name]
            logger.info("Unloaded model: %s", name)

    def unload_all(self) -> None:
        """Unload all models."""
        self._loaded.clear()

    def _load(self, name: str) -> BaseDetectionModel:
        """Instantiate the model from its spec."""
        spec = self._specs[name]
        logger.info("Loading model: %s (backend=%s)", name, spec.backend)

        if spec.backend == ModelBackend.STUB:
            from app.model_registry.models.stub_model import StubDetectionModel
            return StubDetectionModel(spec)

        if spec.backend == ModelBackend.YOLO:
            from app.model_registry.models.yolo_model import YOLODetectionModel
            return YOLODetectionModel(spec)

        raise NotImplementedError(
            f"Backend '{spec.backend}' is not yet implemented. "
            f"Available: YOLO, STUB"
        )

    def health_report(self) -> dict[str, str]:
        """Return health status of all loaded models."""
        return {
            name: model.health()
            for name, model in self._loaded.items()
        }
