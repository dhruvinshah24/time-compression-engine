"""
Pipeline Stage s04: Object Detection — Phase 3B Implementation.

Runs object detection on keyframes produced by s03_scene_detect.
Operates on scene segments for temporal context.

Algorithm: YOLOv8n via ModelRegistry (swappable without code changes).
Full rationale: research/algorithms.md → Phase 3B section.

Success criteria (Phase 3B):
- Returns normalized Detection objects (no raw YOLO output in downstream code)
- Respects confidence threshold from system_settings
- Records model name + version in every Detection
- Records inference timing per frame
- Gracefully handles missing model (stub fallback)
- Unit tests with mocked model pass before real YOLO is installed
"""

import logging
import time

from app.engines.perception.object_detector.config import ObjectDetectorConfig
from app.engines.perception.object_detector.detector import ObjectDetector
from app.model_registry.registry import ModelRegistry
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s04_object_detect"


async def run(context: PipelineContext) -> StageResult:
    """
    Run object detection on keyframes.

    Reads from context:
        metadata["keyframe_paths"]     — selected keyframes (from s03)
        metadata["keyframe_numbers"]   — corresponding frame numbers
        metadata["scene_change_result"] — SceneChangeResult with segments

    Writes to context:
        metadata["detection_result"]     — ObjectDetectionResult
        metadata["frame_detections"]     — list of FrameDetectionResult
        metadata["total_detections"]     — int
        metadata["detected_classes"]     — dict[class_name, count]
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting object detection for job {context.job_id}")

    # ── Step 1: Read keyframes from context ────────────────────────────────
    keyframe_paths = context.metadata.get("keyframe_paths")
    if not keyframe_paths:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["keyframe_paths not found in context — s03_scene_detect must run first"],
            logs=logs,
        )

    keyframe_numbers: list[int] = context.metadata.get("keyframe_numbers", [])
    scene_change_result = context.metadata.get("scene_change_result")
    fps = float(context.metadata.get("fps", 25.0))
    frame_skip_rate = int(context.metadata.get("frame_skip_rate", 5))

    # Build path → frame_number and path → timestamp_ms lookups
    path_to_frame: dict[str, int] = {}
    path_to_ts: dict[str, float] = {}
    if scene_change_result:
        for score in scene_change_result.all_scores:
            path_to_frame[score.frame_path] = score.frame_number
            path_to_ts[score.frame_path] = score.timestamp_ms
    elif keyframe_numbers:
        for path, num in zip(keyframe_paths, keyframe_numbers):
            path_to_frame[path] = num
            path_to_ts[path] = (num * frame_skip_rate * 1000.0) / fps

    logs.append(f"[{STAGE_NAME}] Running detection on {len(keyframe_paths)} keyframes")

    # ── Step 2: Configure from system settings ─────────────────────────────
    model_name = context.settings.get("detection_model_name", "yolov8n")
    confidence = float(context.settings.get("detection_confidence", 0.72))

    config = ObjectDetectorConfig(
        model_name=model_name,
        confidence_threshold=confidence,
    )
    # Override the confidence threshold in the registry spec for this job
    registry = ModelRegistry.instance()
    spec = registry.get_spec(model_name)
    if spec:
        spec.confidence_threshold = confidence

    logs.append(
        f"[{STAGE_NAME}] Model: {model_name}, confidence_threshold: {confidence}"
    )

    # ── Step 3: Run detection ──────────────────────────────────────────────
    detector = ObjectDetector(config=config)

    try:
        result = detector.detect_keyframes(
            keyframe_paths=keyframe_paths,
            keyframe_timestamps=path_to_ts,
            frame_numbers=path_to_frame,
        )
    except ImportError as exc:
        # Model library not installed — fall back to stub
        warnings.append(
            f"Model '{model_name}' not available ({exc}). "
            f"Falling back to stub model — zero detections will be returned."
        )
        logs.append(f"[{STAGE_NAME}] WARNING: {warnings[-1]}")

        # Register stub and retry
        registry.unload(model_name)
        from app.model_registry.registry import STUB_SPEC
        config = ObjectDetectorConfig(model_name="stub")
        detector = ObjectDetector(config=config)
        result = detector.detect_keyframes(
            keyframe_paths=keyframe_paths,
            keyframe_timestamps=path_to_ts,
            frame_numbers=path_to_frame,
        )
    except (KeyboardInterrupt, SystemExit):
        raise  # Never suppress process-level signals in a pipeline stage
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("Object detection failed for job %s", context.job_id)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=[f"Object detection failed: {exc}"],
            logs=logs,
        )

    # ── Step 4: Store in context ───────────────────────────────────────────
    context.metadata["detection_result"] = result
    context.metadata["frame_detections"] = result.frame_results
    context.metadata["total_detections"] = result.total_detections
    context.metadata["detected_classes"] = result.detections_by_class()

    # ── Step 5: Metrics and warnings ───────────────────────────────────────
    if result.total_detections == 0:
        warnings.append(
            "Zero objects detected across all keyframes. "
            "Check confidence threshold or verify video has objects of interest."
        )

    metrics = result.to_metrics_dict()
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Detected {result.total_detections} objects in "
        f"{result.frames_with_detections}/{result.total_frames_processed} frames "
        f"(avg {result.avg_inference_time_ms:.1f}ms/frame)"
    )
    logs.append(
        f"[{STAGE_NAME}] Classes detected: {result.detections_by_class()}"
    )
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms,
        warnings=warnings,
        errors=[],
        metrics=metrics,
        artifacts=[],
        logs=logs,
    )
