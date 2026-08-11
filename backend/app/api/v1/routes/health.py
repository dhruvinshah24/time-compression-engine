"""Health check route — returns engine status + GPU device info."""
from fastapi import APIRouter
from app.engines.perception.frame_extractor.extractor import FrameExtractor

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Returns system health including GPU/CPU inference device status.

    Frontend uses device_info to display the inference device badge:
        CUDA  — RTX 5050 (green)
        CPU   — No GPU detected (yellow)
    """
    extractor = FrameExtractor()

    # ── GPU / device info ──────────────────────────────────────────────────
    device_info: dict = {"cuda_available": False, "device": "cpu"}
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        device_info["cuda_available"] = cuda_ok
        device_info["torch_version"]  = torch.__version__
        if cuda_ok:
            props = torch.cuda.get_device_properties(0)
            device_info.update({
                "device":               "cuda",
                "gpu_name":             torch.cuda.get_device_name(0),
                "vram_gb":              round(props.total_memory / 1e9, 1),
                "cuda_version":         torch.version.cuda,
                "compute_capability":   f"{props.major}.{props.minor}",
            })
        else:
            device_info["device"] = "cpu"
    except Exception as exc:
        device_info["error"] = str(exc)

    # ── Active model info ──────────────────────────────────────────────────
    try:
        from app.model_registry.registry import ModelRegistry
        reg = ModelRegistry.instance()
        loaded = list(reg.health_report().keys())
    except Exception:
        loaded = []

    return {
        "status":      "ok",
        "engines":     [extractor.get_metrics().name],
        "device_info": device_info,
        "loaded_models": loaded,
        "experiment_config": {
            "detection_model": "yolo11x",
            "sahi_enabled":    True,
            "adaptive_skip":   True,
            "per_class_conf":  True,
        },
    }
