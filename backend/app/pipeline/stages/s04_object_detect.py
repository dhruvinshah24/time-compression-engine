"""
Pipeline Stage s04: Object Detection — v1.0.1 Accuracy Overhaul.

Changes from v1.0.0:
  - Quality analysis run on all frames BEFORE detection (analyze_video_quality)
  - Low-light preprocessing applied per-frame based on quality classification
  - UNUSABLE frames skipped (skip_detection=True from low_light.py)
  - Every FrameDetectionResult tagged with lighting_condition + preprocessing_mode
  - Video quality report stored in context for downstream stages (S07, S12)
  - Processing profile applied (QUICK_TEST / SHORT / STANDARD / LONG / EXTENDED)

Algorithm: YOLOv8/YOLO11 via ModelRegistry (swappable without code changes).
Preprocessing: CLAHE on LAB L-channel + gamma correction (low_light.py).
Quality: luminance, blur, dark_pixel_ratio, histogram_spread (quality_analyzer.py).

Full rationale: research/algorithms.md → Phase 3B + v1.0.1 sections.

Success criteria (v1.0.1):
  - Every detection carries quality provenance: quality_class, preprocessing_mode
  - UNUSABLE frames never go to YOLO (no false positive spam from dark noise)
  - LOW_LIGHT frames get CLAHE enhancement before detection
  - VERY_LOW_LIGHT frames get CLAHE + gamma before detection
  - VideoQualityReport available in context.metadata["video_quality_report"]
  - context.frame_quality dict maps frame_path → FrameQuality for S07 use
"""

import logging
import time
from pathlib import Path as _Path
from typing import Optional

from app.engines.perception.object_detector.config import ObjectDetectorConfig
from app.engines.perception.object_detector.detector import ObjectDetector
from app.model_registry.registry import ModelRegistry
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s04_object_detect"

# Sample every Nth frame for quality analysis (not every frame for large videos)
QUALITY_SAMPLE_RATE_DEFAULT = 1   # Analyze every frame by default
QUALITY_SAMPLE_RATE_LONG = 3      # Every 3rd frame for LONG/EXTENDED profiles


async def run(context: PipelineContext) -> StageResult:
    """
    Run object detection on keyframes with quality-aware preprocessing.

    Reads from context:
        metadata["keyframe_paths"]     — selected keyframes (from s03)
        metadata["keyframe_numbers"]   — corresponding frame numbers
        metadata["scene_change_result"] — SceneChangeResult with segments
        metadata["processing_profile"] — QUICK_TEST/SHORT/STANDARD/LONG/EXTENDED

    Writes to context:
        metadata["detection_result"]       — ObjectDetectionResult
        metadata["frame_detections"]       — list of FrameDetectionResult
        metadata["total_detections"]       — int
        metadata["detected_classes"]       — dict[class_name, count]
        metadata["video_quality_report"]   — VideoQualityReport (NEW)
        metadata["frame_quality"]          — dict[frame_path, FrameQuality] (NEW)
        metadata["skipped_unusable_frames"] — count of skipped UNUSABLE frames (NEW)
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting object detection for job {context.job_id}")

    # ── Step 1: Read frames from context ─────────────────────────────────────
    all_frame_paths: list[str] = context.metadata.get("frame_paths", [])
    keyframe_paths: list[str] = context.metadata.get("keyframe_paths") or []
    MIN_FRAMES_FOR_TRACKING = 30

    if len(keyframe_paths) >= MIN_FRAMES_FOR_TRACKING:
        frames_to_detect = keyframe_paths
        frame_source = "s03_keyframes"
    elif all_frame_paths:
        frames_to_detect = all_frame_paths
        frame_source = "all_extracted_frames"
        logs.append(
            f"[{STAGE_NAME}] s03 returned only {len(keyframe_paths)} keyframes — "
            f"falling back to all {len(all_frame_paths)} extracted frames for detection"
        )
    else:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["No frames available — s02_extract and s03_scene_detect must run first"],
            logs=logs,
        )

    scene_change_result = context.metadata.get("scene_change_result")
    fps = float(context.metadata.get("fps", 25.0))
    frame_skip_rate = int(context.metadata.get("frame_skip_rate", 5))
    processing_profile = context.metadata.get("processing_profile", "STANDARD")

    # Build path → frame_number and path → timestamp_ms lookups
    path_to_frame: dict[str, int] = {}
    path_to_ts: dict[str, float] = {}
    if scene_change_result:
        for score in scene_change_result.all_scores:
            path_to_frame[score.frame_path] = score.frame_number
            path_to_ts[score.frame_path] = score.timestamp_ms

    # Fill in any frames not covered by s03 scores
    for idx, path in enumerate(frames_to_detect):
        if path not in path_to_frame:
            stem = _Path(path).stem
            try:
                frame_num = int(stem.split("_")[1]) if stem.startswith("frame_") else idx
            except (IndexError, ValueError):
                frame_num = idx * frame_skip_rate
            path_to_frame[path] = frame_num
            path_to_ts[path] = (frame_num / max(fps, 1.0)) * 1000.0

    logs.append(
        f"[{STAGE_NAME}] Running detection on {len(frames_to_detect)} frames "
        f"(source={frame_source}, profile={processing_profile})"
    )

    # ── Step 2: GPU info log ─────────────────────────────────────────────────
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb  = round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1)
            logs.append(
                f"[{STAGE_NAME}] Inference Device: CUDA | GPU: {gpu_name} | VRAM: {vram_gb}GB"
            )
        else:
            logs.append(f"[{STAGE_NAME}] Inference Device: CPU (no CUDA GPU available)")
    except Exception:
        pass

    # ── Step 3: Quality analysis (NEW) ───────────────────────────────────────
    frame_quality_report = None
    frame_quality_map: dict[str, object] = {}
    skipped_unusable = 0
    quality_sample_rate = (
        QUALITY_SAMPLE_RATE_LONG
        if processing_profile in ("LONG", "EXTENDED")
        else QUALITY_SAMPLE_RATE_DEFAULT
    )

    try:
        from app.utils.quality_analyzer import analyze_video_quality, QualityClass

        frame_nums_list = [path_to_frame.get(p, i) for i, p in enumerate(frames_to_detect)]
        ts_list = [path_to_ts.get(p, 0.0) for p in frames_to_detect]

        frame_quality_report = analyze_video_quality(
            frame_paths=frames_to_detect,
            frame_numbers=frame_nums_list,
            timestamps_ms=ts_list,
            sample_rate=quality_sample_rate,
        )

        # Build path → FrameQuality map
        for fq in frame_quality_report.per_frame:
            if fq.frame_number < len(frames_to_detect):
                frame_quality_map[frames_to_detect[fq.frame_number]] = fq

        # Store in context immediately so S07 can use it
        context.metadata["video_quality_report"] = frame_quality_report
        context.metadata["frame_quality"] = frame_quality_map

        logs.append(
            f"[{STAGE_NAME}] Quality analysis: {frame_quality_report.total_frames} frames | "
            f"dominant={frame_quality_report.dominant_quality_class.value} | "
            f"low_light={frame_quality_report.low_light_ratio:.0%} | "
            f"unusable={frame_quality_report.unusable_ratio:.0%} | "
            f"preprocessing={frame_quality_report.recommended_preprocessing}"
        )

        if frame_quality_report.unusable_ratio > 0.5:
            warnings.append(
                f"More than {frame_quality_report.unusable_ratio:.0%} of frames are UNUSABLE "
                f"(mean_lum={frame_quality_report.mean_luminance:.1f}). "
                "Detection results will be sparse. Check video source illumination."
            )
    except ImportError:
        logs.append(f"[{STAGE_NAME}] quality_analyzer not available — skipping quality pass")
    except Exception as exc:
        logs.append(f"[{STAGE_NAME}] Quality analysis failed ({exc}) — proceeding without it")

    # ── Step 4: Configure detection ──────────────────────────────────────────
    model_name = context.settings.get("detection_model", "yolo11x")
    confidence = float(context.settings.get("detection_confidence", 0.20))
    per_class_conf: dict = context.settings.get("per_class_confidence", {})
    default_conf = per_class_conf.get("default", confidence)
    use_sahi      = bool(context.settings.get("use_sahi", False))
    sahi_tile_size = int(context.settings.get("sahi_tile_size", 640))
    sahi_overlap   = float(context.settings.get("sahi_overlap", 0.2))

    config = ObjectDetectorConfig(model_name=model_name, confidence_threshold=confidence)
    logs.append(
        f"[{STAGE_NAME}] Model: {model_name} | conf: {confidence} | "
        f"SAHI: {'ON tile=' + str(sahi_tile_size) if use_sahi else 'OFF'}"
    )

    # ── Step 5: Low-light preprocessing + detection loop (NEW) ─────────────
    # Instead of sending all frames to detect_keyframes() at once,
    # we run per-frame preprocessing then batch-detect.
    # This is the core integration: quality → preprocess → detect.

    # Try to import preprocessing (graceful fallback if not installed)
    try:
        import cv2 as _cv2
        from app.utils.quality_analyzer import QualityClass as _QC, FrameQuality as _FQ
        from app.utils.low_light import preprocess_frame as _preprocess_frame
        preprocess_available = True
    except ImportError:
        preprocess_available = False
        logs.append(f"[{STAGE_NAME}] low_light/cv2 not available — raw frames used")

    # Build the final list of frames to send to YOLO
    # For each frame: if quality says UNUSABLE → skip, else apply preprocessing
    frames_after_preprocess: list[str] = []  # Paths of preprocessed/original frames to detect
    preprocessing_metadata: dict[str, dict] = {}  # path → {quality_class, preprocessing_mode}
    preprocessed_tmp_dir: Optional[str] = None

    if preprocess_available and frame_quality_map:
        import tempfile, os
        preprocessed_tmp_dir = tempfile.mkdtemp(prefix=f"tce_preproc_{context.job_id}_")
        logs.append(f"[{STAGE_NAME}] Preprocessing frames (low-light mode active)...")

        for frame_path in frames_to_detect:
            fq = frame_quality_map.get(frame_path)

            if fq is None:
                # Frame not analyzed (outside sample window) — treat as NORMAL
                frames_after_preprocess.append(frame_path)
                preprocessing_metadata[frame_path] = {
                    "quality_class": "normal",
                    "preprocessing_mode": "off",
                    "skipped": False,
                }
                continue

            # Skip UNUSABLE frames
            if fq.quality_class.value == "unusable":
                skipped_unusable += 1
                preprocessing_metadata[frame_path] = {
                    "quality_class": "unusable",
                    "preprocessing_mode": "off",
                    "skipped": True,
                    "mean_luminance": fq.mean_luminance,
                    "blur_score": fq.blur_score,
                }
                continue

            # NORMAL → no preprocessing
            if fq.recommended_preprocessing == "off":
                frames_after_preprocess.append(frame_path)
                preprocessing_metadata[frame_path] = {
                    "quality_class": fq.quality_class.value,
                    "preprocessing_mode": "off",
                    "skipped": False,
                    "mean_luminance": fq.mean_luminance,
                }
                continue

            # LOW_LIGHT or VERY_LOW_LIGHT → apply enhancement
            try:
                frame_bgr = _cv2.imread(frame_path)
                if frame_bgr is None:
                    frames_after_preprocess.append(frame_path)
                    continue

                preprocessed = _preprocess_frame(frame_bgr, fq, mode="auto")

                if preprocessed.skip_detection:
                    # Reclassified as skip after preprocessing check
                    skipped_unusable += 1
                    preprocessing_metadata[frame_path] = {
                        "quality_class": fq.quality_class.value,
                        "preprocessing_mode": "off",
                        "skipped": True,
                    }
                    continue

                # Save preprocessed frame to temp dir
                fname = _Path(frame_path).name
                tmp_path = os.path.join(preprocessed_tmp_dir, fname)
                _cv2.imwrite(tmp_path, preprocessed.frame, [_cv2.IMWRITE_JPEG_QUALITY, 95])
                frames_after_preprocess.append(tmp_path)

                preprocessing_metadata[frame_path] = {
                    "quality_class": fq.quality_class.value,
                    "preprocessing_mode": preprocessed.preprocessing_mode,
                    "skipped": False,
                    "original_mean_lum": preprocessed.original_mean_lum,
                    "enhanced_mean_lum": preprocessed.enhanced_mean_lum,
                }
            except Exception as exc:
                logger.debug("Preprocessing failed for %s: %s", frame_path, exc)
                frames_after_preprocess.append(frame_path)
                preprocessing_metadata[frame_path] = {
                    "quality_class": fq.quality_class.value,
                    "preprocessing_mode": "off",
                    "skipped": False,
                    "error": str(exc),
                }

        n_enhanced = sum(
            1 for v in preprocessing_metadata.values()
            if v.get("preprocessing_mode", "off") not in ("off", "")
        )
        logs.append(
            f"[{STAGE_NAME}] Preprocessing complete: "
            f"{len(frames_after_preprocess)} frames to detect | "
            f"{skipped_unusable} UNUSABLE skipped | "
            f"{n_enhanced} enhanced (CLAHE/gamma)"
        )
    else:
        # No preprocessing available — use original frames
        frames_after_preprocess = list(frames_to_detect)
        for fp in frames_to_detect:
            preprocessing_metadata[fp] = {"quality_class": "unknown", "preprocessing_mode": "off"}

    if not frames_after_preprocess:
        warnings.append("All frames were UNUSABLE — no frames sent to detector.")
        frames_after_preprocess = list(frames_to_detect)  # Last resort: try anyway

    context.metadata["skipped_unusable_frames"] = skipped_unusable
    context.metadata["preprocessing_metadata"] = preprocessing_metadata

    # Rebuild frame number/timestamp maps for preprocessed paths
    preproc_to_frame: dict[str, int] = {}
    preproc_to_ts: dict[str, float] = {}
    if preprocessed_tmp_dir:
        for tmp_path in frames_after_preprocess:
            fname = _Path(tmp_path).name
            # Original path has same filename
            orig_path = str(_Path(frames_to_detect[0]).parent / fname) if frames_to_detect else tmp_path
            preproc_to_frame[tmp_path] = path_to_frame.get(orig_path, path_to_frame.get(tmp_path, 0))
            preproc_to_ts[tmp_path] = path_to_ts.get(orig_path, path_to_ts.get(tmp_path, 0.0))
    else:
        preproc_to_frame = path_to_frame
        preproc_to_ts = path_to_ts

    # ── Step 6: Run YOLO detection ───────────────────────────────────────────
    detector = ObjectDetector(config=config)

    if use_sahi:
        try:
            from app.utils.sahi_detector import SAHIDetector, SAHIConfig
            raw_model = ModelRegistry.instance().get(model_name)
            sahi_cfg  = SAHIConfig(
                enabled=True,
                tile_size=sahi_tile_size,
                overlap_ratio=sahi_overlap,
                nms_iou_threshold=0.50,
            )
            sahi_wrapper = SAHIDetector(raw_model, sahi_cfg)
            logs.append(f"[{STAGE_NAME}] SAHI wrapper active")
        except Exception as exc:
            logs.append(f"[{STAGE_NAME}] SAHI init failed ({exc}) — using standard inference")
            use_sahi = False

    try:
        result = detector.detect_keyframes(
            keyframe_paths=frames_after_preprocess,
            keyframe_timestamps=preproc_to_ts,
            frame_numbers=preproc_to_frame,
            override_confidence=confidence,
        )
    except ImportError as exc:
        warnings.append(
            f"Model '{model_name}' not available ({exc}). "
            f"Falling back to stub model — zero detections will be returned."
        )
        logs.append(f"[{STAGE_NAME}] WARNING: {warnings[-1]}")
        config = ObjectDetectorConfig(model_name="stub")
        detector = ObjectDetector(config=config)
        result = detector.detect_keyframes(
            keyframe_paths=frames_after_preprocess,
            keyframe_timestamps=preproc_to_ts,
            frame_numbers=preproc_to_frame,
        )
    except (KeyboardInterrupt, SystemExit):
        raise
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

    # ── Step 7: Tag each FrameDetectionResult with quality provenance (NEW) ──
    # Attach lighting_condition and preprocessing_mode to each frame result.
    # S07 and S08 can then use this to discount low-light detections.
    for fdr in result.frame_results:
        fp = getattr(fdr, "frame_path", "")
        meta = preprocessing_metadata.get(fp, {})
        fdr.lighting_condition = meta.get("quality_class", "normal")
        fdr.preprocessing_mode = meta.get("preprocessing_mode", "off")

    # ── Step 8: Per-class confidence filtering ───────────────────────────────
    if per_class_conf:
        pre_filter_count = result.total_detections
        for fdr in result.frame_results:
            filtered = []
            for det in fdr.detections:
                cls_threshold = per_class_conf.get(
                    det.class_name.lower().replace("_", " "),
                    per_class_conf.get(det.class_name.lower(), default_conf)
                )
                if det.confidence >= cls_threshold:
                    filtered.append(det)
            fdr.detections = filtered
        new_total = sum(len(fdr.detections) for fdr in result.frame_results)
        logs.append(
            f"[{STAGE_NAME}] Per-class confidence filter: "
            f"{pre_filter_count} → {new_total} detections"
        )

    # ── Step 9: Store in context ──────────────────────────────────────────────
    context.metadata["detection_result"]   = result
    context.metadata["frame_detections"]   = result.frame_results
    context.metadata["total_detections"]   = sum(len(f.detections) for f in result.frame_results)
    context.metadata["detected_classes"]   = result.detections_by_class()

    # Build frame_number → path dict for ReID crop extractor (s05)
    frame_paths_by_number: dict[int, str] = {}
    for fdr in result.frame_results:
        fn = getattr(fdr, "frame_number", None)
        fp = getattr(fdr, "frame_path", None)
        if fn is not None and fp:
            # Map back to original (pre-preprocessing) path for crop extraction
            orig_fp = fp
            if preprocessed_tmp_dir and fp.startswith(preprocessed_tmp_dir):
                fname = _Path(fp).name
                orig_fp = str(_Path(frames_to_detect[0]).parent / fname) if frames_to_detect else fp
            frame_paths_by_number[fn] = orig_fp

    if not frame_paths_by_number:
        for path_str in frames_to_detect:
            stem = _Path(path_str).stem
            try:
                fn = int(stem.split("_")[-1])
            except (ValueError, IndexError):
                fn = len(frame_paths_by_number)
            frame_paths_by_number[fn] = path_str
    context.metadata["frame_paths"] = frame_paths_by_number

    # Clean up temp preprocessing directory
    if preprocessed_tmp_dir:
        try:
            import shutil
            shutil.rmtree(preprocessed_tmp_dir, ignore_errors=True)
        except Exception:
            pass

    # ── Step 10: Metrics and warnings ─────────────────────────────────────────
    if result.total_detections == 0:
        warnings.append(
            "Zero objects detected across all keyframes. "
            "Check confidence threshold or verify video has objects of interest."
        )

    metrics = result.to_metrics_dict()

    # Add quality metrics to stage metrics
    if frame_quality_report:
        metrics.update({
            "quality_dominant": frame_quality_report.dominant_quality_class.value,
            "quality_mean_luminance": frame_quality_report.mean_luminance,
            "quality_mean_blur": frame_quality_report.mean_blur_score,
            "quality_low_light_ratio": frame_quality_report.low_light_ratio,
            "quality_unusable_ratio": frame_quality_report.unusable_ratio,
            "quality_preprocessing": frame_quality_report.recommended_preprocessing,
            "skipped_unusable_frames": skipped_unusable,
        })

    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Detected {result.total_detections} objects in "
        f"{result.frames_with_detections}/{result.total_frames_processed} frames "
        f"(avg {result.avg_inference_time_ms:.1f}ms/frame)"
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
