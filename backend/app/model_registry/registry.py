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
    YOLO  = "yolo"
    WORLD = "world"   # YOLO-World open-vocabulary
    DINO  = "dino"
    RTDETR = "rtdetr"
    STUB  = "stub"


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

YOLOV8M_SPEC = ModelSpec(
    name="yolov8m",
    backend=ModelBackend.YOLO,
    version="8.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.18,
    description="YOLOv8 Medium — 80 fixed COCO classes. mAP 50.2.",
)

YOLOV8L_SPEC = ModelSpec(
    name="yolov8l",
    backend=ModelBackend.YOLO,
    version="8.0.0",
    weight_path=None,  # auto-downloads yolov8l.pt (~87MB)
    input_size=(640, 640),
    confidence_threshold=0.25,
    description="YOLOv8 Large — best accuracy for CCTV person tracking. mAP 52.9. ~87MB.",
)

YOLOV8X_SPEC = ModelSpec(
    name="yolov8x",
    backend=ModelBackend.YOLO,
    version="8.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.18,
    description="YOLOv8 Extra-Large — highest COCO accuracy. mAP 53.9. ~136MB.",
)

# ── YOLO-World: open-vocabulary, detects ANY object via text prompts ─────────
# No retraining required. Uses 200+ class vocabulary from WORLD_VOCABULARY.
# Reference: Cheng et al., Tencent AI Lab, CVPR 2024.
YOLOWORLD_S_SPEC = ModelSpec(
    name="yolov8s-worldv2",
    backend=ModelBackend.WORLD,
    version="2.0.0",
    weight_path=None,   # auto-downloads yolov8s-worldv2.pt (~45MB)
    input_size=(640, 640),
    confidence_threshold=0.15,
    description="YOLO-World Small — open-vocabulary, fast. Detects wallet, pen, safe, etc.",
)

YOLOWORLD_L_SPEC = ModelSpec(
    name="yolov8l-worldv2",
    backend=ModelBackend.WORLD,
    version="2.0.0",
    weight_path=None,   # auto-downloads yolov8l-worldv2.pt (~100MB)
    input_size=(640, 640),
    confidence_threshold=0.15,
    description="YOLO-World Large — open-vocabulary, best accuracy. 200+ custom classes.",
)

STUB_SPEC = ModelSpec(
    name="stub",
    backend=ModelBackend.STUB,
    version="0.0.0",
    description="Stub model — returns empty detections. Used when no model is installed.",
)

# ── YOLO11 family (Ultralytics 2024 — successor to YOLOv8) ──────────────────────────
YOLO11N_SPEC = ModelSpec(
    name="yolo11n",
    backend=ModelBackend.YOLO,
    version="11.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.20,
    description="YOLO11 Nano — 2.6M params, 6.5 GFLOPs. Fastest, Experiment A baseline.",
)

YOLO11S_SPEC = ModelSpec(
    name="yolo11s",
    backend=ModelBackend.YOLO,
    version="11.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.20,
    description="YOLO11 Small — 9.4M params, 21.5 GFLOPs. mAP 47.0. Experiment B.",
)

YOLO11M_SPEC = ModelSpec(
    name="yolo11m",
    backend=ModelBackend.YOLO,
    version="11.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.20,
    description="YOLO11 Medium — 20.1M params, 68.0 GFLOPs. mAP 51.5. Experiment C.",
)

YOLO11L_SPEC = ModelSpec(
    name="yolo11l",
    backend=ModelBackend.YOLO,
    version="11.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.20,
    description="YOLO11 Large — 25.3M params, 86.9 GFLOPs. mAP 53.4. Experiment D.",
)

YOLO11X_SPEC = ModelSpec(
    name="yolo11x",
    backend=ModelBackend.YOLO,
    version="11.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.20,
    description="YOLO11 Extra-Large — 56.9M params, 194.9 GFLOPs. mAP 54.7. Max accuracy.",
)

YOLO11X_POSE_SPEC = ModelSpec(
    name="yolo11x-pose",
    backend=ModelBackend.YOLO,
    version="11.0.0",
    weight_path=None,
    input_size=(640, 640),
    confidence_threshold=0.20,
    description="YOLO11x Pose — 57M params + 17 keypoints. For crawling/posture detection.",
)

# ---------------------------------------------------------------------------
# Model Profiles — benchmarked on RTX 5050 (8.55GB VRAM, CC 12.0)
# Benchmark date: 2026-08-25
# Results: yolo11n=80fps, yolo11s=57fps, yolo11m=40fps, yolo11l=32fps, yolo11x=32fps
# yolo11l and yolo11x run at the same speed on RTX 5050.
# Default is yolo11x (best accuracy, same speed as yolo11l on this hardware).
# ---------------------------------------------------------------------------
MODEL_PROFILES: dict[str, dict] = {
    "fast": {
        "model": "yolo11n",
        "description": "80 fps @ 1080p. 44MB VRAM. Best for real-time or low-power.",
        "vram_required_mb": 100,
    },
    "balanced": {
        "model": "yolo11m",
        "description": "40 fps @ 1080p. 127MB VRAM. Good accuracy/speed balance.",
        "vram_required_mb": 300,
    },
    "accuracy": {
        "model": "yolo11x",
        "description": "32 fps @ 1080p. 392MB VRAM. Best mAP 54.7. Recommended.",
        "vram_required_mb": 800,
    },
    "pose": {
        "model": "yolo11x-pose",
        "description": "32 fps @ 1080p + 17 keypoints. For crawling/activity detection.",
        "vram_required_mb": 900,
    },
}

# Fallback chain: accuracy → balanced → fast
_PROFILE_FALLBACK: dict[str, str] = {
    "accuracy": "balanced",
    "pose":     "accuracy",
    "balanced": "fast",
    "fast":     "fast",  # no further fallback
}

_BUILTIN_SPECS: dict[str, ModelSpec] = {
    # YOLOv8 family (fixed-class COCO, ordered by size)
    "yolov8n":          YOLOV8N_SPEC,
    "yolov8s":          YOLOV8S_SPEC,
    "yolov8m":          YOLOV8M_SPEC,
    "yolov8l":          YOLOV8L_SPEC,
    "yolov8x":          YOLOV8X_SPEC,
    # YOLO11 family (2024 — better accuracy, same COCO 80 classes)
    "yolo11n":          YOLO11N_SPEC,
    "yolo11s":          YOLO11S_SPEC,
    "yolo11m":          YOLO11M_SPEC,
    "yolo11l":          YOLO11L_SPEC,
    "yolo11x":          YOLO11X_SPEC,   # ← Default accuracy profile (mAP 54.7)
    "yolo11x-pose":     YOLO11X_POSE_SPEC,  # ← Pose profile (keypoints)
    # Open-vocabulary YOLO-World models (for object inventory panel)
    "yolov8s-worldv2":  YOLOWORLD_S_SPEC,
    "yolov8l-worldv2":  YOLOWORLD_L_SPEC,
    # Stub
    "stub":             STUB_SPEC,
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

    def get_model(self, name: str) -> "BaseDetectionModel | None":
        """
        Return a loaded model instance, or None if not registered.
        Alias for get() that returns None instead of raising KeyError.
        Used by BenchmarkRunner and other non-pipeline callers.
        """
        if name not in self._specs:
            logger.warning("[Registry] Model '%s' not registered", name)
            return None
        return self.get(name)

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

        if spec.backend == ModelBackend.WORLD:
            from app.model_registry.models.yolo_model import YOLOWorldDetectionModel
            return YOLOWorldDetectionModel(spec)

        raise NotImplementedError(
            f"Backend '{spec.backend}' is not yet implemented. "
            f"Available: YOLO, WORLD, STUB"
        )

    def get_for_profile(self, profile: str) -> "BaseDetectionModel":
        """
        Return a model for the given profile ('fast', 'balanced', 'accuracy', 'pose').

        Checks available VRAM before loading. If VRAM is insufficient, automatically
        falls back to the next lighter profile. Records the fallback in logs.

        Args:
            profile: One of 'fast', 'balanced', 'accuracy', 'pose'.

        Returns:
            Loaded BaseDetectionModel for the resolved profile.
        """
        resolved = profile
        while True:
            if resolved not in MODEL_PROFILES:
                logger.warning("[Registry] Unknown profile '%s', falling back to 'fast'", resolved)
                resolved = "fast"

            prof = MODEL_PROFILES[resolved]
            model_name = prof["model"]
            vram_required_mb = prof["vram_required_mb"]

            # Check VRAM availability
            try:
                import torch
                if torch.cuda.is_available():
                    free_mb = (
                        torch.cuda.get_device_properties(0).total_memory
                        - torch.cuda.memory_allocated(0)
                    ) / 1e6
                    if free_mb < vram_required_mb:
                        next_profile = _PROFILE_FALLBACK.get(resolved, "fast")
                        if next_profile == resolved:
                            # No further fallback
                            logger.warning(
                                "[Registry] Profile '%s' needs %.0fMB VRAM, only %.0fMB free. "
                                "Loading anyway (last resort).",
                                resolved, vram_required_mb, free_mb,
                            )
                            break
                        logger.warning(
                            "[Registry] Profile '%s' needs %.0fMB VRAM, only %.0fMB free. "
                            "Falling back to '%s'.",
                            resolved, vram_required_mb, free_mb, next_profile,
                        )
                        resolved = next_profile
                        continue
            except Exception:
                pass  # CUDA not available — proceed anyway
            break

        model_name = MODEL_PROFILES[resolved]["model"]
        if model_name not in self._specs:
            logger.warning("[Registry] Model '%s' not in specs, using stub", model_name)
            model_name = "stub"

        if resolved != profile:
            logger.info("[Registry] Profile '%s' → resolved to '%s' (%s)", profile, resolved, model_name)

        return self.get(model_name)

    def health_report(self) -> dict[str, str]:
        """Return health status of all loaded models."""
        return {
            name: model.health()
            for name, model in self._loaded.items()
        }

