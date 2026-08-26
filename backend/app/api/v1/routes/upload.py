"""
Upload route — Time Compression Engine v1.0.1.

POST /api/v1/upload/
  - Accepts multipart: file + source_domain + model_profile
  - Saves file to disk
  - Probes video metadata with ffprobe
  - Creates Video + Job records (InMemory)
  - Starts the pipeline as a background task
  - Returns full metadata immediately (no waiting for pipeline)

Phase 3: model_profile param added.
  fast     → YOLO11n detection, no pose (80 FPS @ 1080p, measured RTX 5050)
  balanced → YOLO11l detection, yolov8n-pose (32 FPS @ 1080p, measured RTX 5050)
  accuracy → YOLO11x detection, yolo11x-pose (32 FPS @ 1080p, measured RTX 5050)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.pipeline.context import PipelineContext
from app.pipeline.orchestrator import PipelineOrchestrator
from app.repositories.inmemory import get_event_repo, get_job_repo, get_video_repo
from app.utils.ffmpeg import (
    FFmpegNotFoundError,
    VideoCorruptedError,
    get_processing_profile,
    probe_video,
)
from app.utils.storage import get_upload_path

router = APIRouter()
logger = logging.getLogger(__name__)


def _job_id() -> str:
    now = datetime.now(timezone.utc)
    return f"JOB-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _video_id() -> str:
    return f"VID-{uuid.uuid4().hex[:12].upper()}"


# ── Model profile registry ─────────────────────────────────────────────────────
# FPS and VRAM values are MEASURED on RTX 5050 @ 1080p, CUDA 13.2, 2026-08-25.
# Do not present these as estimates or theoretical values.
_MODEL_PROFILES: dict[str, dict] = {
    "fast": {
        "detection_model": "yolo11n",
        "pose_model":      None,          # Pose disabled — too slow for 80fps throughput
        "fps_measured":    80,
        "vram_mb":         44,
        "description":     "YOLO11n @ 80 FPS. Lower detection accuracy. Best for exploratory analysis or high-throughput screening.",
    },
    "balanced": {
        "detection_model": "yolo11l",
        "pose_model":      "yolov8n-pose",
        "fps_measured":    32,
        "vram_mb":         183,
        "description":     "YOLO11l @ 32 FPS. Good accuracy/throughput balance. Recommended for general CCTV processing.",
    },
    "accuracy": {
        "detection_model": "yolo11x",
        "pose_model":      "yolo11x-pose",  # Phase 3 upgrade from yolov8n-pose
        "fps_measured":    32,
        "vram_mb":         392,
        "description":     "YOLO11x @ 32 FPS. Maximum detection quality. Higher compute cost. Same throughput as Balanced on RTX 5050.",
    },
}

_DEFAULT_PROFILE = "accuracy"


@router.post("/")
async def upload_video(
    file: UploadFile = File(...),
    source_domain: str = Form(default="general"),
    model_profile: str = Form(default=_DEFAULT_PROFILE),
):
    """
    Accept a video upload, probe its metadata, and start the TCE pipeline.

    Returns immediately with job ID and video metadata. The pipeline runs
    in the background. Poll GET /api/v1/jobs/{job_id} for progress.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    video_id = _video_id()
    job_id = _job_id()

    # ── Resolve model profile → concrete model names ───────────────────────
    if model_profile not in _MODEL_PROFILES:
        logger.warning(
            "[%s] Unknown model_profile=%r, defaulting to %r",
            job_id, model_profile, _DEFAULT_PROFILE,
        )
        model_profile = _DEFAULT_PROFILE
    profile_cfg = _MODEL_PROFILES[model_profile]
    resolved_detection_model = profile_cfg["detection_model"]
    resolved_pose_model = profile_cfg["pose_model"]

    logger.info(
        "[%s] Upload received: %s (domain=%s, profile=%s, detection=%s, pose=%s)",
        job_id, file.filename, source_domain,
        model_profile, resolved_detection_model, resolved_pose_model or "disabled",
    )

    # ── 1. Save file to disk ───────────────────────────────────────────────
    try:
        content = await file.read()
        dest_path = get_upload_path(job_id, file.filename)
        import hashlib as _hashlib
        sha256 = _hashlib.sha256(content).hexdigest()
        with open(dest_path, "wb") as f_out:
            f_out.write(content)
        file_size_bytes = len(content)
    except Exception as exc:
        logger.exception("[%s] Failed to save upload", job_id)
        raise HTTPException(status_code=500, detail=f"File save failed: {exc}") from exc

    logger.info("[%s] Saved %d bytes → %s", job_id, file_size_bytes, dest_path)

    # ── 2. Probe video metadata ────────────────────────────────────────────
    ffprobe_available = True
    try:
        meta = probe_video(dest_path)
        profile_info = get_processing_profile(
            duration_seconds=meta.duration_seconds,
            fps=meta.fps,
            frame_skip_rate=5,
        )
        video_meta_dict = meta.to_dict()
        video_meta_dict["source_domain"] = source_domain
        video_meta_dict["sha256"] = sha256
        video_meta_dict.update(profile_info)
    except FFmpegNotFoundError:
        logger.warning("[%s] ffprobe not found — using basic file metadata", job_id)
        ffprobe_available = False
        video_meta_dict = {
            "filename":             file.filename,
            "file_size_bytes":      file_size_bytes,
            "source_domain":        source_domain,
            "sha256":               sha256,
            "duration_seconds":     None,
            "fps":                  None,
            "frame_count":          None,
            "resolution":           "unknown",
            "codec":                "unknown",
            "profile":              "Unknown (ffprobe not installed)",
            "estimated_frames":     None,
            "estimated_processing_s": None,
            "duration_hms":         "--:--:--",
        }
        profile_info = {}
    except (VideoCorruptedError, Exception) as exc:
        logger.error("[%s] Probe failed: %s", job_id, exc)
        raise HTTPException(status_code=422, detail=f"Video probe failed: {exc}") from exc

    logger.info("[%s] Probe: %s", job_id, video_meta_dict.get("profile", "unknown"))

    # ── 3. Create Video + Job records ──────────────────────────────────────
    video_repo = get_video_repo()
    job_repo = get_job_repo()
    event_repo = get_event_repo()

    video_record = {
        "id":              video_id,
        "filename":        file.filename,
        "file_path":       str(dest_path),
        "file_size_bytes": file_size_bytes,
        "source_domain":   source_domain,
        "metadata":        video_meta_dict,
    }
    await video_repo.create(video_record)

    # Build the initial stage list for the Inspector (all pending)
    from app.pipeline.orchestrator import STAGE_LABELS, _STAGE_MODULES
    initial_stages = [
        {
            "name":        m.split(".")[-1],
            "label":       STAGE_LABELS.get(m.split(".")[-1], m.split(".")[-1]),
            "status":      "pending",
            "duration_ms": None,
            "metrics":     {},
            "errors":      [],
        }
        for m in _STAGE_MODULES
    ]

    job_record = {
        "id":                   job_id,
        "video_id":             video_id,
        "filename":             file.filename,
        "status":               "queued",
        "progress":             0,
        "current_stage":        None,
        "current_stage_label":  None,
        "failed_stage":         None,
        "error":                None,
        "stages":               initial_stages,
        "logs":                 [],
        "event_count":          0,
        "video_metadata":       video_meta_dict,
        "ffprobe_available":    ffprobe_available,
        # Phase 3: model selection recorded for research evaluation
        "model_profile":        model_profile,
        "detection_model":      resolved_detection_model,
        "pose_model":           resolved_pose_model,
    }
    await job_repo.create(job_record)

    # ── 4. Start pipeline in background ───────────────────────────────────
    output_dir = str(dest_path.parent)
    context = PipelineContext(
        job_id=job_id,
        video_id=video_id,
        video_path=str(dest_path),
        output_dir=output_dir,
        settings={
            "source_domain":    source_domain,
            "model_profile":    model_profile,    # stored for research evaluation

            # ── Frame extraction ─────────────────────────────────────────────
            # frame_skip_rate: fixed fallback used by S02 before adaptive skip.
            # adaptive_skip: when True, S02 runs pre-extraction MOG2 streaming
            # to select only needed frame indices before calling FFmpeg.
            "frame_skip_rate":              3,
            "adaptive_skip":                True,
            "adaptive_skip_min":            1,
            "adaptive_skip_max":            10,

            # ── Detection model ───────────────────────────────────────────────
            # Resolved from model_profile. FPS measured on RTX 5050 @ 1080p.
            "detection_model":              resolved_detection_model,
            "detection_confidence":         0.20,

            # ── Per-class confidence thresholds ──────────────────────────────
            "per_class_confidence": {
                "person":    0.20,
                "man":       0.20,
                "woman":     0.20,
                "child":     0.18,
                "bicycle":   0.22,
                "car":       0.25,
                "motorcycle":0.22,
                "laptop":    0.17,
                "cell phone":0.15,
                "phone":     0.15,
                "bottle":    0.15,
                "cup":       0.15,
                "book":      0.17,
                "backpack":  0.18,
                "handbag":   0.18,
                "default":   0.20,
            },

            # ── SAHI sliced inference ─────────────────────────────────────────
            "use_sahi":                     True,
            "sahi_tile_size":               640,
            "sahi_overlap":                 0.2,

            # ── Tracker ──────────────────────────────────────────────────────
            "tracker_max_lost":             15,
            "tracker_iou_threshold":        0.25,
            "tracker_min_confirm":          2,

            # ── ReID ──────────────────────────────────────────────────────────
            "reid_similarity_threshold":    0.52,

            # ── Event understanding ────────────────────────────────────────────
            "event_min_confidence":         0.30,
            "event_min_track_frames":       3,
            "event_suppress_camera_motion": True,

            # ── Pose estimation ────────────────────────────────────────────────
            # fast=None (disabled), balanced=yolov8n-pose, accuracy=yolo11x-pose
            "pose_model":                   resolved_pose_model,
            "pose_confidence":              0.30,
            "pose_min_consecutive":         3,

            # ── Brightness ────────────────────────────────────────────────────
            "brightness_threshold":         15.0,
        },
    )

    orchestrator = PipelineOrchestrator(job_repo=job_repo, event_repo=event_repo)

    async def run_pipeline() -> None:
        try:
            await orchestrator.run(context)
        except Exception as exc:
            logger.exception("[%s] Pipeline crashed", job_id)
            await job_repo.update(job_id, {
                "status": "failed",
                "error":  f"Pipeline crashed: {exc}",
            })

    asyncio.create_task(run_pipeline())
    logger.info("[%s] Pipeline queued as background task", job_id)

    # ── 5. Return immediately ──────────────────────────────────────────────
    return {
        "video_id":        video_id,
        "job_id":          job_id,
        "filename":        file.filename,
        "status":          "queued",
        "model_profile":   model_profile,
        "detection_model": resolved_detection_model,
        "metadata":        video_meta_dict,
    }
