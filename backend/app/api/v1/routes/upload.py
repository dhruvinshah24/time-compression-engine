"""
Upload route — Time Compression Engine v1.0.1.

POST /api/v1/upload/
  - Accepts multipart: file + source_domain
  - Saves file to disk
  - Probes video metadata with ffprobe
  - Creates Video + Job records (InMemory)
  - Starts the pipeline as a background task
  - Returns full metadata immediately (no waiting for pipeline)
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


@router.post("/")
async def upload_video(
    file: UploadFile = File(...),
    source_domain: str = Form(default="general"),
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

    logger.info("[%s] Upload received: %s (domain=%s)", job_id, file.filename, source_domain)

    # ── 1. Save file to disk ───────────────────────────────────────────────
    try:
        # Read entire file into memory first (safe for video uploads up to STORAGE limit)
        content = await file.read()
        dest_path = get_upload_path(job_id, file.filename)
        import hashlib as _hashlib
        hasher = _hashlib.sha256()
        hasher.update(content)
        sha256 = hasher.hexdigest()
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
            "filename": file.filename,
            "file_size_bytes": file_size_bytes,
            "source_domain": source_domain,
            "sha256": sha256,
            "duration_seconds": None,
            "fps": None,
            "frame_count": None,
            "resolution": "unknown",
            "codec": "unknown",
            "profile": "Unknown (ffprobe not installed)",
            "estimated_frames": None,
            "estimated_processing_s": None,
            "duration_hms": "--:--:--",
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
        "id":            video_id,
        "filename":      file.filename,
        "file_path":     str(dest_path),
        "file_size_bytes": file_size_bytes,
        "source_domain": source_domain,
        "metadata":      video_meta_dict,
    }
    await video_repo.create(video_record)

    # Build the initial stage list for the Inspector (all pending)
    from app.pipeline.orchestrator import STAGE_LABELS, _STAGE_MODULES
    initial_stages = [
        {
            "name":    m.split(".")[-1],
            "label":   STAGE_LABELS.get(m.split(".")[-1], m.split(".")[-1]),
            "status":  "pending",
            "duration_ms": None,
            "metrics": {},
            "errors":  [],
        }
        for m in _STAGE_MODULES
    ]

    job_record = {
        "id":               job_id,
        "video_id":         video_id,
        "filename":         file.filename,
        "status":           "queued",
        "progress":         0,
        "current_stage":    None,
        "current_stage_label": None,
        "failed_stage":     None,
        "error":            None,
        "stages":           initial_stages,
        "logs":             [],
        "event_count":      0,
        "video_metadata":   video_meta_dict,
        "ffprobe_available": ffprobe_available,
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
            "source_domain":       source_domain,

            # ── Frame extraction (adaptive skip) ────────────────────────────
            # Adaptive skip uses MOG2 motion analysis to vary sampling rate:
            #   static room → skip=10 (~1fps), running → skip=1 (full fps).
            # Experiment A baseline: fixed skip=3. Experiment D: adaptive=True.
            "frame_skip_rate":     3,            # fixed fallback / warmup
            "adaptive_skip":       True,         # enable motion-adaptive skipping
            "adaptive_skip_min":   1,
            "adaptive_skip_max":   10,

            # ── Detection model ─────────────────────────────────────────────
            # Experiment framework — switchable via system_settings:
            #   yolov8l  → mAP 52.9  (v1.0 baseline)
            #   yolo11m  → mAP 51.5  (Experiment B: architecture upgrade)
            #   yolo11l  → mAP 53.4  (Experiment C)
            #   yolo11x  → mAP 54.7  (Experiment D: maximum accuracy)
            "detection_model":     "yolo11x",
            "detection_confidence": 0.20,

            # ── Per-class confidence (JSON string, data-driven) ───────────────
            # Lower thresholds for small/hard-to-detect objects.
            # Parsed in s04_object_detect.py — edit without code changes.
            "per_class_confidence": {
                "person":        0.20,  # must catch all people
                "man":           0.20,
                "woman":         0.20,
                "child":         0.18,
                "bicycle":       0.22,
                "car":           0.25,
                "motorcycle":    0.22,
                "laptop":        0.17,  # reflective screens reduce score
                "cell phone":    0.15,  # small, often partially visible
                "phone":         0.15,
                "bottle":        0.15,  # small, round
                "cup":           0.15,
                "book":          0.17,
                "backpack":      0.18,
                "handbag":       0.18,
                "default":       0.20,
            },

            # ── SAHI sliced inference ────────────────────────────────────────
            # Experiment C/D: tiles frame into 640×640 patches so small objects
            # (person 15m away = 8×20px) become 80×200px within their tile.
            "use_sahi":           True,
            "sahi_tile_size":     640,
            "sahi_overlap":       0.2,  # 20% tile overlap to avoid edge misses

            # ── Tracker ─────────────────────────────────────────────────────
            "tracker_max_lost":    15,
            "tracker_iou_threshold": 0.25,
            "tracker_min_confirm": 2,

            # ── ReID ────────────────────────────────────────────────────────
            "reid_similarity_threshold": 0.52,

            # ── Event understanding ──────────────────────────────────────────
            "event_min_confidence": 0.30,
            "event_min_track_frames": 3,
            "event_suppress_camera_motion": True,

            # ── Pose estimation ──────────────────────────────────────────────
            "pose_model":          "yolov8n-pose",
            "pose_confidence":     0.30,
            "pose_min_consecutive": 3,
            # ── Brightness ──────────────────────────────────────────────────
            "brightness_threshold": 15.0,
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
                "error": f"Pipeline crashed: {exc}",
            })

    asyncio.create_task(run_pipeline())
    logger.info("[%s] Pipeline queued as background task", job_id)

    # ── 5. Return immediately ──────────────────────────────────────────────
    return {
        "video_id":   video_id,
        "job_id":     job_id,
        "filename":   file.filename,
        "status":     "queued",
        "metadata":   video_meta_dict,
    }
