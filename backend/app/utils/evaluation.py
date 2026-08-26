"""
Research Evaluation Framework — Time Compression Engine v1.0.1.

Provides a structured EvaluationMatrix dataclass for recording real
pipeline results across different videos and configurations.

IMPORTANT: Do NOT fill evaluation fields with invented numbers.
This module provides the schema and export utilities only.
Actual metric values come from running the pipeline on real footage.

Ground-truth metrics (precision, recall, F1, ID switches) are ONLY
populated when labelled ground truth exists for the video.
"""

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class EvaluationMatrix:
    """
    Structured evaluation record for one TCE pipeline run on one video.

    Validation status meanings:
      PROVEN          — measured on real hardware with real footage and ground truth
      PARTIALLY_VALIDATED — measured on real footage but without ground truth
      NOT_YET_VALIDATED  — code exists and unit tests pass, but no real-footage test
    """

    # ── Video identity ────────────────────────────────────────────────────
    video_id:              str
    video_source:          str              # "VIRAT_Ground", "synthetic", "youtube", etc.
    duration_seconds:      Optional[float]  = None
    resolution:            Optional[str]    = None   # e.g. "1920x1080"
    fps:                   Optional[float]  = None
    scene_type:            Optional[str]    = None   # "outdoor_parking", "corridor", etc.
    lighting_condition:    Optional[str]    = None   # "daylight", "low_light", etc.
    num_persons_approx:    Optional[int]    = None

    # ── Configuration ─────────────────────────────────────────────────────
    model_profile:         Optional[str]    = None   # "fast", "balanced", "accuracy"
    detection_model:       Optional[str]    = None   # "yolo11x", "yolo11l", etc.
    pose_model:            Optional[str]    = None   # "yolo11x-pose", None, etc.
    adaptive_skip_enabled: bool             = False
    sahi_enabled:          bool             = False
    low_light_enabled:     bool             = False
    roi_zones_configured:  int              = 0

    # ── Frame statistics ──────────────────────────────────────────────────
    total_video_frames:    Optional[int]    = None
    frames_processed:      Optional[int]    = None
    frames_skipped:        Optional[int]    = None
    effective_sampling_ratio: Optional[float] = None
    low_light_frames:      Optional[int]    = None
    unusable_frames:       Optional[int]    = None

    # ── Detection results ─────────────────────────────────────────────────
    total_detections:      Optional[int]    = None
    unique_tracks:         Optional[int]    = None
    confirmed_tracks:      Optional[int]    = None

    # ── Event results ─────────────────────────────────────────────────────
    events_generated:      Optional[int]    = None
    events_by_type:        dict             = field(default_factory=dict)

    # ── System performance ────────────────────────────────────────────────
    processing_time_seconds: Optional[float] = None
    real_time_factor:      Optional[float]  = None   # processing_time / video_duration
    processing_fps:        Optional[float]  = None
    inference_fps:         Optional[float]  = None

    # ── Tracking quality (where measurable) ───────────────────────────────
    # These require tracking annotations or heuristic counting.
    track_continuity_score: Optional[float] = None   # fraction with same ID maintained
    id_switches:            Optional[int]   = None
    track_fragmentation:    Optional[float] = None

    # ── Ground truth metrics (ONLY when labelled GT available) ────────────
    ground_truth_available: bool            = False
    detection_precision:    Optional[float] = None
    detection_recall:       Optional[float] = None
    detection_f1:           Optional[float] = None
    event_precision:        Optional[float] = None
    event_recall:           Optional[float] = None
    event_f1:               Optional[float] = None

    # ── Validation classification ──────────────────────────────────────────
    validation_status:     str              = "NOT_YET_VALIDATED"
    failures:              list             = field(default_factory=list)
    notes:                 str              = ""

    # ── Metadata ──────────────────────────────────────────────────────────
    evaluated_at:          str              = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    job_id:                Optional[str]    = None


def evaluate_job(job_record: dict, video_metadata: dict | None = None) -> EvaluationMatrix:
    """
    Build an EvaluationMatrix from a completed job record.

    Only populates fields that have real data from the job.
    Does not compute or invent any metric values.
    """
    matrix = EvaluationMatrix(
        video_id=job_record.get("video_id", "unknown"),
        video_source="tce_pipeline",
        job_id=job_record.get("id"),
        model_profile=job_record.get("model_profile"),
        detection_model=job_record.get("detection_model"),
        pose_model=job_record.get("pose_model"),
    )

    # Populate from video metadata
    if video_metadata:
        matrix.duration_seconds = video_metadata.get("duration_seconds")
        matrix.resolution       = video_metadata.get("resolution")
        matrix.fps              = video_metadata.get("fps")

    # Walk stage metrics
    for stage in job_record.get("stages", []):
        m    = stage.get("metrics", {}) or {}
        name = stage.get("name", "")

        if name == "s02_extract":
            matrix.total_video_frames = m.get("estimated_frames")
            matrix.frames_processed   = m.get("frames_extracted")
            matrix.adaptive_skip_enabled = bool(m.get("adaptive_skip_enabled", False))
            if asc := m.get("adaptive_skip_stats"):
                matrix.effective_sampling_ratio = asc.get("effective_sampling_ratio")
                matrix.frames_skipped = asc.get("frames_skipped")

        elif name == "s04_object_detect":
            matrix.total_detections  = m.get("total_detections")
            matrix.low_light_frames  = m.get("low_light_frames")
            matrix.unusable_frames   = m.get("unusable_frames_skipped")
            matrix.sahi_enabled      = bool(m.get("sahi_enabled", False))

        elif name == "s07_event_understand":
            matrix.events_generated  = m.get("total_events")
            matrix.events_by_type    = m.get("event_types") or {}

    # Compute performance metrics from available data
    total_ms = sum(
        (s.get("duration_ms") or 0) for s in job_record.get("stages", [])
    )
    if total_ms > 0:
        matrix.processing_time_seconds = total_ms / 1000.0
        if matrix.duration_seconds and matrix.duration_seconds > 0:
            matrix.real_time_factor = matrix.processing_time_seconds / matrix.duration_seconds
        if matrix.frames_processed and matrix.processing_time_seconds:
            matrix.processing_fps = round(
                matrix.frames_processed / matrix.processing_time_seconds, 2
            )

    return matrix


def export_evaluation_json(matrix: EvaluationMatrix, output_path: str | Path) -> None:
    """Export evaluation matrix as JSON."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(asdict(matrix), f, indent=2, default=str)


def export_evaluation_csv(
    matrices: list[EvaluationMatrix],
    output_path: str | Path,
) -> None:
    """Export multiple evaluation matrices as CSV for research logging."""
    if not matrices:
        return
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    flat_rows = []
    for m in matrices:
        row = asdict(m)
        flat: dict = {}
        for k, v in row.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    flat[f"{k}.{kk}"] = vv
            elif isinstance(v, list):
                flat[k] = ";".join(str(x) for x in v)
            else:
                flat[k] = v
        flat_rows.append(flat)

    if flat_rows:
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=flat_rows[0].keys())
            writer.writeheader()
            writer.writerows(flat_rows)
