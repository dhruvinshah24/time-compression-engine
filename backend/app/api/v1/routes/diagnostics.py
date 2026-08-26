"""
Diagnostics API — Time Compression Engine v1.0.1.

GET /api/v1/jobs/{job_id}/diagnostics
  Returns per-stage metrics, frame statistics, adaptive skip stats,
  detection counts, event counts, and export info for a completed job.

GET /api/v1/jobs/{job_id}/evaluation
  Returns a structured EvaluationMatrix for research logging.

Design principle:
  Only returns data that actually exists in the job record.
  Fields not present are returned as null — NEVER invented.
  This endpoint exists to support research evaluation, not marketing.
"""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from app.repositories.inmemory import get_job_repo

router = APIRouter()


def _stage_by_name(stages: list, name: str) -> dict:
    """Find a stage dict by name, returns {} if not found."""
    return next((s for s in stages if s.get("name") == name), {})


@router.get("/{job_id}/diagnostics")
async def get_job_diagnostics(job_id: str):
    """
    Return structured diagnostics for a job.

    All fields may be null if the corresponding stage has not run
    or did not produce that metric.
    """
    repo = get_job_repo()
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    stages = job.get("stages", [])

    # ── Aggregate stage timing ──────────────────────────────────────────────
    stage_summary = [
        {
            "name":        s.get("name"),
            "label":       s.get("label"),
            "status":      s.get("status"),
            "duration_ms": s.get("duration_ms"),
            "error_count": len(s.get("errors", [])),
        }
        for s in stages
    ]

    total_ms = sum(
        s.get("duration_ms") or 0
        for s in stages
        if s.get("duration_ms") is not None
    )

    # ── S02: Frame extraction ───────────────────────────────────────────────
    s02 = _stage_by_name(stages, "s02_extract")
    s02m = s02.get("metrics", {})
    frame_stats = {
        "processing_profile":       s02m.get("processing_profile"),
        "frames_extracted":         s02m.get("frames_extracted"),
        "frame_reduction_ratio":    s02m.get("frame_reduction_ratio"),
        "extraction_speed_fps":     s02m.get("extraction_speed_fps"),
        "adaptive_skip_enabled":    s02m.get("adaptive_skip_enabled", False),
        "skip_source":              s02m.get("skip_source"),
        "adaptive_skip_stats":      s02m.get("adaptive_skip_stats"),
        # Flattened adaptive metrics
        "frames_examined_for_motion": s02m.get("frames_examined_for_motion"),
        "frames_selected":          s02m.get("frames_selected"),
        "frames_skipped_by_adaptive": s02m.get("frames_skipped_by_adaptive"),
        "effective_sampling_ratio": s02m.get("effective_sampling_ratio"),
        "avg_motion_score_pct":     s02m.get("avg_motion_score_pct"),
        "max_motion_score_pct":     s02m.get("max_motion_score_pct"),
        "protected_windows":        s02m.get("protected_windows"),
    }

    # ── S04: Detection ──────────────────────────────────────────────────────
    s04 = _stage_by_name(stages, "s04_object_detect")
    s04m = s04.get("metrics", {})
    detection_stats = {
        "total_detections":          s04m.get("total_detections"),
        "frames_with_detections":    s04m.get("frames_with_detections"),
        "low_light_frames":          s04m.get("low_light_frames"),
        "unusable_frames_skipped":   s04m.get("unusable_frames_skipped"),
        "frames_preprocessed":       s04m.get("frames_preprocessed"),
        "model_used":                s04m.get("detection_model"),
        "sahi_enabled":              s04m.get("sahi_enabled"),
        "video_quality_summary":     s04m.get("video_quality_summary"),
    }

    # ── S07: Event understanding ────────────────────────────────────────────
    s07 = _stage_by_name(stages, "s07_event_understand")
    s07m = s07.get("metrics", {})
    event_stats = {
        "total_events":             s07m.get("total_events"),
        "event_types":              s07m.get("event_types", {}),
        "roi_events":               s07m.get("roi_events"),
        "pose_temporal_events":     s07m.get("pose_temporal_events"),
        "crawling_events":          s07m.get("crawling_events"),
        "running_events":           s07m.get("running_events"),
    }

    # ── S12: Export ─────────────────────────────────────────────────────────
    s12 = _stage_by_name(stages, "s12_export")
    s12m = s12.get("metrics", {})
    export_stats = {
        "kept_events":              s12m.get("kept_events"),
        "thumbnails_generated":     s12m.get("thumbnails_generated"),
        "clips_generated":          s12m.get("clips_generated"),
        "ffmpeg_available":         s12m.get("ffmpeg_available"),
        "story_coherence_score":    s12m.get("story_coherence_score"),
    }

    # ── Model info (from job record) ────────────────────────────────────────
    model_info = {
        "model_profile":   job.get("model_profile"),
        "detection_model": job.get("detection_model"),
        "pose_model":      job.get("pose_model"),
    }

    return {
        "job_id":             job_id,
        "status":             job.get("status"),
        "total_processing_ms": total_ms if total_ms > 0 else None,
        "model_info":         model_info,
        "frame_stats":        frame_stats,
        "detection_stats":    detection_stats,
        "event_stats":        event_stats,
        "export_stats":       export_stats,
        "stage_summary":      stage_summary,
        "note": (
            "All null values indicate the corresponding stage has not run "
            "or did not produce that metric. No values are invented."
        ),
    }


@router.get("/{job_id}/evaluation")
async def get_job_evaluation(job_id: str):
    """
    Return a structured EvaluationMatrix for research logging.

    Only populates fields that have real data. Does not compute or invent
    ground-truth metrics — those require external annotation data.
    """
    from app.utils.evaluation import evaluate_job
    repo = get_job_repo()
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    matrix = evaluate_job(job, job.get("video_metadata"))
    return asdict(matrix)
