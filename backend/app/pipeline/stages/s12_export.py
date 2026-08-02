"""
Pipeline Stage s12: Export — Phase 10 Implementation.

This is the final stage of the Time Compression Engine pipeline.

Responsibilities:
  1. Run NarrativeValidator — final consistency gate before export
  2. Generate the decision manifest — full explainability at the compression level
  3. Generate FFmpeg clip specifications — one per kept event
  4. Produce the concat manifest for assembling the highlight video
  5. Save the summary JSON for the frontend

The "decision manifest" (per mentor recommendation):
  Every segment decision is documented with its importance, narrative, and policy.
  This extends the explainability philosophy all the way to the final output.

  {
    "segment_id": "seg_7_a3f1c2",
    "decision": "kept",
    "importance": 0.72,
    "narrative": 0.95,
    "policy": "complete_chain_preserved"
  }

FFmpeg export:
  Phase 10 generates the FFmpeg commands. Actual video extraction runs
  when FFmpeg is available (checked via ffmpeg.py utility).
  On systems without FFmpeg, the manifest is saved and clips are skipped.
"""

import json
import logging
import time
from pathlib import Path

from app.engines.temporal.story_preservation.sequence_validator import NarrativeValidator
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s12_export"


async def run(context: PipelineContext) -> StageResult:
    """
    Run narrative validation, generate decision manifest, produce export spec.

    Reads from context:
        metadata["summary_events"]       — kept events from s11
        metadata["kept_event_ids"]       — set of kept event IDs
        metadata["compression_result"]   — CompressionResult from s11
        metadata["ranking_result"]       — RankingResult from s10
        metadata["story_segments"]       — all segments from s09
        metadata["event_graph"]          — EventGraph from s09

    Writes to context:
        metadata["validation_report"]    — NarrativeValidator output
        metadata["decision_manifest"]    — list of segment decision dicts
        metadata["export_manifest"]      — full export manifest (clips + concat)
        metadata["export_manifest_path"] — path to saved JSON file
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting export for job {context.job_id}")

    # ── Step 1: Read inputs ────────────────────────────────────────────────
    summary_events = context.metadata.get("summary_events", [])
    kept_event_ids: set[str] = context.metadata.get("kept_event_ids", set())
    compression_result = context.metadata.get("compression_result")
    ranking_result = context.metadata.get("ranking_result")
    story_segments = context.metadata.get("story_segments", [])
    event_graph = context.metadata.get("event_graph")

    if not summary_events:
        warnings.append("No summary events — export manifest will be empty.")

    # ── Step 2: Narrative Validation ───────────────────────────────────────
    logs.append(f"[{STAGE_NAME}] Running NarrativeValidator...")
    validator = NarrativeValidator()

    # Build kept segments from story_segments that have at least one kept event
    kept_segments = [
        seg for seg in story_segments
        if any(e.event_id in kept_event_ids for e in seg.events)
    ]

    all_events_by_id = {
        e.event_id: e
        for seg in story_segments
        for e in seg.events
    }

    validation_report = validator.validate(
        kept_segments=kept_segments,
        kept_event_ids=kept_event_ids,
        event_graph=event_graph,
        all_events_by_id=all_events_by_id,
    )
    context.metadata["validation_report"] = validation_report

    if not validation_report.is_valid:
        for issue in validation_report.errors():
            warnings.append(f"[NARRATIVE ERROR] {issue.check}: {issue.description}")
        logs.append(
            f"[{STAGE_NAME}] Validation FAILED: "
            f"{len(validation_report.errors())} errors, "
            f"{len(validation_report.warnings())} warnings"
        )
    else:
        logs.append(
            f"[{STAGE_NAME}] Validation passed "
            f"({validation_report.complete_chains_intact}/{validation_report.chains_checked} "
            f"complete chains intact, "
            f"{len(validation_report.warnings())} warnings)"
        )

    # ── Step 3: Decision manifest ──────────────────────────────────────────
    logs.append(f"[{STAGE_NAME}] Building decision manifest...")
    decision_manifest: list[dict] = []

    if ranking_result and compression_result:
        for rs in ranking_result.ranked_segments:
            # Find the CompressionDecision for the first event in this segment
            seg_decisions = [
                d for d in compression_result.decisions
                if d.segment_id == rs.segment.segment_id
            ]
            if seg_decisions:
                first_decision = seg_decisions[0]
                decision_manifest.append({
                    "segment_id": rs.segment.segment_id,
                    "decision": "kept" if first_decision.keep else "discarded",
                    "completeness": rs.segment.completeness.value,
                    "event_count": rs.segment.event_count,
                    "duration_ms": rs.segment.duration_ms,
                    "importance": round(rs.importance_score, 4),
                    "narrative": round(rs.narrative_score, 4),
                    "combined_rank": round(rs.combined_rank, 4),
                    "rank": rs.rank,
                    "policy": first_decision.reason,
                })

    context.metadata["decision_manifest"] = decision_manifest
    logs.append(f"[{STAGE_NAME}] {len(decision_manifest)} segment decisions recorded")

    # ── Step 4: FFmpeg clip specifications ─────────────────────────────────
    logs.append(f"[{STAGE_NAME}] Generating clip specifications...")
    clips: list[dict] = []

    video_path = context.video_path
    output_dir = Path(context.output_dir) / context.job_id / "clips"

    for i, event in enumerate(summary_events, start=1):
        start_s = event.start_ms / 1000.0
        end_s = event.end_ms / 1000.0
        clip_filename = f"clip_{i:03d}_{event.event_type}.mp4"
        clip_path = str(output_dir / clip_filename)

        clips.append({
            "clip_index": i,
            "clip_path": clip_path,
            "event_id": event.event_id,
            "event_type": event.event_type,
            "track_id": event.track_id,
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "duration_ms": event.end_ms - event.start_ms,
            "confidence": round(event.confidence, 4),
            "ffmpeg_command": (
                f"ffmpeg -i \"{video_path}\" "
                f"-ss {start_s:.3f} -to {end_s:.3f} "
                f"-c:v libx264 -c:a aac "
                f"\"{clip_path}\""
            ),
        })

    # Concat manifest for assembling highlight video
    concat_list_path = str(output_dir / "clips.txt")
    highlight_output = str(Path(context.output_dir) / context.job_id / "highlight.mp4")
    concat_command = (
        f"ffmpeg -f concat -safe 0 -i \"{concat_list_path}\" "
        f"-c copy \"{highlight_output}\""
    )

    # ── Step 5: Full export manifest ───────────────────────────────────────
    total_duration_ms = sum(c["duration_ms"] for c in clips)
    export_manifest = {
        "job_id": context.job_id,
        "video_id": context.video_id,
        "source_video": video_path,
        "narrative_validation": {
            "is_valid": validation_report.is_valid,
            "errors": len(validation_report.errors()),
            "warnings": len(validation_report.warnings()),
            "complete_chains_intact": validation_report.complete_chains_intact,
        },
        "summary": {
            "total_kept_events": len(summary_events),
            "total_duration_ms": total_duration_ms,
            "compression_ratio": round(
                len(kept_event_ids) / len(all_events_by_id), 4
            ) if all_events_by_id else 0.0,
        },
        "segment_decisions": decision_manifest,
        "clips": clips,
        "assembly": {
            "concat_list_path": concat_list_path,
            "highlight_output": highlight_output,
            "concat_command": concat_command,
        },
    }
    context.metadata["export_manifest"] = export_manifest

    # ── Step 6: Save manifest to disk ─────────────────────────────────────
    manifest_path: str | None = None
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = str(Path(context.output_dir) / context.job_id / "export_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(export_manifest, f, indent=2)
        context.metadata["export_manifest_path"] = manifest_path
        logs.append(f"[{STAGE_NAME}] Manifest saved to {manifest_path}")
    except OSError as e:
        warnings.append(f"Could not save manifest: {e}")

    # ── Step 7: Metrics ────────────────────────────────────────────────────
    metrics = {
        "kept_events": len(summary_events),
        "total_clips": len(clips),
        "total_clip_duration_ms": total_duration_ms,
        "narrative_validation_passed": validation_report.is_valid,
        "validation_errors": len(validation_report.errors()),
        "validation_warnings": len(validation_report.warnings()),
        "complete_chains_intact": validation_report.complete_chains_intact,
        "decision_manifest_entries": len(decision_manifest),
    }
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] {len(clips)} clips specified, "
        f"{total_duration_ms:.0f}ms total highlight duration"
    )
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms,
        warnings=warnings,
        errors=[],
        metrics=metrics,
        artifacts=[manifest_path] if manifest_path else [],
        logs=logs,
    )
