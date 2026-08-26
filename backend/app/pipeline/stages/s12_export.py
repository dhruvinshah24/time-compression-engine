"""
Pipeline Stage s12: Export — v1.0.1 Accuracy Overhaul.

Changes from v1.0.0:
  - Generates real annotated event thumbnails using frame_annotator.py
  - Generates before/event/after frames for each important event
  - Stores thumbnail paths on event evidence (accessible via API)
  - Actually executes FFmpeg clips (not just spec strings) when FFmpeg is available
  - Static output structure: outputs/{job_id}/thumbnails/, clips/, annotated/
  - Processing duration profile stored in manifest
  - Video quality report summary included in manifest

Responsibilities:
  1. NarrativeValidator — final consistency gate before export
  2. Decision manifest — full explainability at the compression level
  3. Event thumbnails — real annotated frames from frame_annotator
  4. Before/event/after frames — context frames for event preview modal
  5. FFmpeg clip execution (if ffmpeg available) or spec-only fallback
  6. Export manifest (JSON) with all paths
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

# Thumbnail max width (pixels) — smaller = faster, larger = better quality
THUMBNAIL_MAX_WIDTH = 640


async def run(context: PipelineContext) -> StageResult:
    """
    Run narrative validation, generate thumbnails, produce export manifest.

    Reads from context:
        metadata["summary_events"]       — kept events from s11
        metadata["kept_event_ids"]       — set of kept event IDs
        metadata["compression_result"]   — CompressionResult from s11
        metadata["ranking_result"]       — RankingResult from s10
        metadata["story_segments"]       — all segments from s09
        metadata["event_graph"]          — EventGraph from s09
        metadata["frame_paths"]          — {frame_number: path} dict (s04)
        metadata["video_quality_report"] — VideoQualityReport (s04, optional)

    Writes to context:
        metadata["validation_report"]    — NarrativeValidator output
        metadata["decision_manifest"]    — list of segment decision dicts
        metadata["export_manifest"]      — full export manifest (clips + concat)
        metadata["export_manifest_path"] — path to saved JSON file
        metadata["thumbnails_generated"] — count of thumbnails generated
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
    video_quality_report = context.metadata.get("video_quality_report")
    processing_profile = context.metadata.get("processing_profile", "STANDARD")

    if not summary_events:
        warnings.append("No summary events — export manifest will be empty.")

    # ── Step 2: Narrative Validation ───────────────────────────────────────
    logs.append(f"[{STAGE_NAME}] Running NarrativeValidator...")
    validator = NarrativeValidator()

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

    # ── Step 3: Output directory setup ────────────────────────────────────
    job_output_dir = Path(context.output_dir) / context.job_id
    thumbnails_dir = job_output_dir / "thumbnails"
    annotated_dir  = job_output_dir / "annotated"
    clips_dir      = job_output_dir / "clips"

    for d in [thumbnails_dir, annotated_dir, clips_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Step 4: Build ordered frame list for before/event/after lookup ────
    frame_paths_raw = context.metadata.get("frame_paths", {})
    fps = float(context.metadata.get("fps", 25.0))

    # Normalize to sorted list of (frame_number, path) tuples
    if isinstance(frame_paths_raw, dict):
        ordered_frames = sorted(
            [(int(k), str(v)) for k, v in frame_paths_raw.items()],
            key=lambda x: x[0]
        )
    else:
        ordered_frames = []
        for i, p in enumerate(frame_paths_raw):
            stem = Path(str(p)).stem
            try:
                fn = int(stem.split("_")[-1])
            except (ValueError, IndexError):
                fn = i
            ordered_frames.append((fn, str(p)))
        ordered_frames.sort(key=lambda x: x[0])

    all_frame_numbers = [fn for fn, _ in ordered_frames]
    all_frame_paths   = [fp for _, fp in ordered_frames]
    all_timestamps_ms = [fn / max(fps, 1.0) * 1000.0 for fn in all_frame_numbers]

    logs.append(f"[{STAGE_NAME}] {len(all_frame_paths)} frames available for thumbnail generation")

    # ── Step 5: Generate event thumbnails (NEW) ────────────────────────────
    thumbnails_generated = 0
    roi_zones_cfg = context.settings.get("roi_zones", [])

    try:
        from app.utils.frame_annotator import (
            generate_event_thumbnail,
            generate_before_event_after,
        )
        annotator_available = True
    except ImportError:
        annotator_available = False
        logs.append(f"[{STAGE_NAME}] frame_annotator not available — skipping thumbnails")

    for event in summary_events:
        event_frame = getattr(event, "start_frame", None)
        event_ms    = getattr(event, "start_ms", 0.0)
        event_type  = getattr(event, "event_type", "unknown_event")
        event_conf  = getattr(event, "confidence", 0.5)
        event_id    = getattr(event, "event_id", str(id(event)))

        # Get bbox from evidence if available
        evidence = getattr(event, "evidence", {}) or {}
        bbox_norm = evidence.get("bbox_norm") or evidence.get("bbox")
        track_label = evidence.get("person_label") or f"Track {getattr(event, 'track_id', '?')}"

        # Find closest frame to event timestamp
        if not all_frame_paths:
            continue

        if event_frame is not None:
            # Find by frame number
            closest_idx = min(
                range(len(all_frame_numbers)),
                key=lambda i: abs(all_frame_numbers[i] - event_frame)
            )
        else:
            # Find by timestamp
            closest_idx = min(
                range(len(all_timestamps_ms)),
                key=lambda i: abs(all_timestamps_ms[i] - event_ms)
            )

        event_frame_path = all_frame_paths[closest_idx]
        event_ts = all_timestamps_ms[closest_idx]

        if annotator_available and Path(event_frame_path).exists():
            try:
                # a. Main event thumbnail
                thumb_path = str(thumbnails_dir / f"{event_id}_thumb.jpg")
                generate_event_thumbnail(
                    frame_path=event_frame_path,
                    event_type=event_type,
                    event_confidence=event_conf,
                    timestamp_ms=event_ts,
                    output_path=thumb_path,
                    bbox_norm=bbox_norm,
                    track_label=track_label,
                    roi_zones=roi_zones_cfg if roi_zones_cfg else None,
                    max_width=THUMBNAIL_MAX_WIDTH,
                )

                # Store path on event evidence for API access
                event.evidence["thumbnail_path"] = thumb_path

                # b. Before / event / after frames
                bea = generate_before_event_after(
                    frame_paths=all_frame_paths,
                    frame_numbers=all_frame_numbers,
                    event_frame=event_frame or closest_idx,
                    event_type=event_type,
                    event_confidence=event_conf,
                    output_dir=str(thumbnails_dir),
                    event_id=event_id,
                    timestamps_ms=all_timestamps_ms,
                    pre_post_count=2,  # 2 frames before and after
                )

                event.evidence["before_frame_path"] = bea.get("before")
                event.evidence["event_frame_path"]  = bea.get("event")
                event.evidence["after_frame_path"]  = bea.get("after")

                thumbnails_generated += 1

            except FileNotFoundError:
                pass  # Frame file doesn't exist — skip silently
            except Exception as exc:
                logger.debug("Thumbnail generation failed for %s: %s", event_id, exc)

    context.metadata["thumbnails_generated"] = thumbnails_generated
    logs.append(f"[{STAGE_NAME}] Generated {thumbnails_generated} event thumbnails")

    # ── Step 6: Decision manifest ──────────────────────────────────────────
    logs.append(f"[{STAGE_NAME}] Building decision manifest...")
    decision_manifest: list[dict] = []

    if ranking_result and compression_result:
        for rs in ranking_result.ranked_segments:
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

    # ── Step 7: FFmpeg clip specifications + optional execution ────────────
    logs.append(f"[{STAGE_NAME}] Generating clip specifications...")
    clips: list[dict] = []
    clips_executed = 0

    video_path = context.video_path

    # Check if ffmpeg is available for actual clip extraction
    ffmpeg_available = False
    try:
        import subprocess
        result_check = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, timeout=3
        )
        ffmpeg_available = result_check.returncode == 0
    except Exception:
        ffmpeg_available = False

    for i, event in enumerate(summary_events, start=1):
        start_s = max(0.0, event.start_ms / 1000.0 - 0.5)  # 0.5s pre-roll
        end_s   = event.end_ms / 1000.0 + 0.5              # 0.5s post-roll
        clip_filename = f"clip_{i:03d}_{event.event_type}.mp4"
        clip_path = str(clips_dir / clip_filename)

        evidence = getattr(event, "evidence", {}) or {}
        clip_entry = {
            "clip_index": i,
            "clip_path": clip_path,
            "event_id": event.event_id,
            "event_type": event.event_type,
            "track_id": event.track_id,
            "start_ms": event.start_ms,
            "end_ms": event.end_ms,
            "duration_ms": event.end_ms - event.start_ms,
            "confidence": round(event.confidence, 4),
            "thumbnail_path": evidence.get("thumbnail_path"),
            "before_frame_path": evidence.get("before_frame_path"),
            "event_frame_path": evidence.get("event_frame_path"),
            "after_frame_path": evidence.get("after_frame_path"),
            "ffmpeg_command": (
                f'ffmpeg -i "{video_path}" '
                f"-ss {start_s:.3f} -to {end_s:.3f} "
                f"-c:v libx264 -c:a aac "
                f'"{clip_path}"'
            ),
            "clip_generated": False,
        }

        # Execute clip if ffmpeg is available
        if ffmpeg_available and Path(video_path).exists():
            try:
                import subprocess
                subprocess.run(
                    ["ffmpeg", "-y", "-i", video_path,
                     "-ss", str(start_s), "-to", str(end_s),
                     "-c:v", "libx264", "-c:a", "aac",
                     clip_path],
                    capture_output=True, timeout=60
                )
                if Path(clip_path).exists() and Path(clip_path).stat().st_size > 0:
                    clip_entry["clip_generated"] = True
                    clips_executed += 1
                    event.evidence["clip_path"] = clip_path
            except Exception as exc:
                logger.debug("Clip generation failed for event %s: %s", event.event_id, exc)

        clips.append(clip_entry)

    concat_list_path = str(clips_dir / "clips.txt")
    highlight_output = str(job_output_dir / "highlight.mp4")
    concat_command = (
        f'ffmpeg -f concat -safe 0 -i "{concat_list_path}" '
        f'-c copy "{highlight_output}"'
    )

    logs.append(
        f"[{STAGE_NAME}] {len(clips)} clips specified, "
        f"{clips_executed} actually generated (ffmpeg={'available' if ffmpeg_available else 'not found'})"
    )

    # ── Step 8: Full export manifest ──────────────────────────────────────
    total_duration_ms = sum(c["duration_ms"] for c in clips)

    quality_summary = {}
    if video_quality_report:
        quality_summary = video_quality_report.summary_dict()

    export_manifest = {
        "job_id": context.job_id,
        "video_id": context.video_id,
        "source_video": video_path,
        "processing_profile": processing_profile,
        "video_quality": quality_summary,
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
            "thumbnails_generated": thumbnails_generated,
            "clips_generated": clips_executed,
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

    # ── Step 9: Save manifest to disk ─────────────────────────────────────
    manifest_path: str | None = None
    try:
        manifest_path = str(job_output_dir / "export_manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(export_manifest, f, indent=2, default=str)
        context.metadata["export_manifest_path"] = manifest_path
        logs.append(f"[{STAGE_NAME}] Manifest saved to {manifest_path}")
    except OSError as e:
        warnings.append(f"Could not save manifest: {e}")

    # ── Step 10: Metrics ──────────────────────────────────────────────────
    metrics = {
        "kept_events": len(summary_events),
        "total_clips": len(clips),
        "clips_generated": clips_executed,
        "total_clip_duration_ms": total_duration_ms,
        "thumbnails_generated": thumbnails_generated,
        "narrative_validation_passed": validation_report.is_valid,
        "validation_errors": len(validation_report.errors()),
        "validation_warnings": len(validation_report.warnings()),
        "complete_chains_intact": validation_report.complete_chains_intact,
        "decision_manifest_entries": len(decision_manifest),
        "ffmpeg_available": ffmpeg_available,
    }
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms_total = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] {len(clips)} clips, "
        f"{thumbnails_generated} thumbnails, "
        f"{total_duration_ms:.0f}ms total highlight duration"
    )
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms_total}ms")

    return StageResult(
        success=True,
        stage_name=STAGE_NAME,
        duration_ms=duration_ms_total,
        warnings=warnings,
        errors=[],
        metrics=metrics,
        artifacts=[manifest_path] if manifest_path else [],
        logs=logs,
    )
