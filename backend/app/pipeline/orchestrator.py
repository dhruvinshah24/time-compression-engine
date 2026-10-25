"""
Pipeline Orchestrator — Time Compression Engine v1.0.1.

Runs stages s01–s12 sequentially. After each stage:
  - logs a structured entry
  - updates the job record in the repository
  - stops if the stage reports failure

Usage:
    orchestrator = PipelineOrchestrator(job_repo, event_repo)
    await orchestrator.run(context)

The caller creates the job record before calling run(); this module
only updates it as stages complete.
"""

import asyncio
import importlib
import logging
import time
import uuid
from typing import Any

from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)

# Ordered list of stage module import paths
_STAGE_MODULES = [
    "app.pipeline.stages.s01_upload",
    "app.pipeline.stages.s02_extract",
    "app.pipeline.stages.s03_scene_detect",
    "app.pipeline.stages.s04_object_detect",
    "app.pipeline.stages.s05_track",
    "app.pipeline.stages.s06_motion_analyze",
    "app.pipeline.stages.s07_event_understand",
    "app.pipeline.stages.s08_confidence_fuse",
    "app.pipeline.stages.s09_story_build",
    "app.pipeline.stages.s10_rank",
    "app.pipeline.stages.s11_summarize",
    "app.pipeline.stages.s12_export",
]

# Human-readable names for the Pipeline Inspector
STAGE_LABELS = {
    "s01_upload":          "Upload & Validate",
    "s02_extract":         "Frame Extraction",
    "s03_scene_detect":    "Scene Detection",
    "s04_object_detect":   "Object Detection",
    "s05_track":           "Object Tracking",
    "s06_motion_analyze":  "Motion Analysis",
    "s07_event_understand":"Event Understanding",
    "s08_confidence_fuse": "Confidence Fusion",
    "s09_story_build":     "Story Builder",
    "s10_rank":            "Event Ranking",
    "s11_summarize":       "Compression Policy",
    "s12_export":          "Export & Manifest",
}


class PipelineOrchestrator:
    """
    Sequential pipeline runner.

    Injects no business logic — delegates entirely to the stage modules.
    Responsibility: ordering, error handling, job record updates, logging.
    """

    def __init__(self, job_repo: Any, event_repo: Any) -> None:
        self._job_repo = job_repo
        self._event_repo = event_repo

    async def run(self, context: PipelineContext) -> bool:
        """
        Execute s01 → s12 in order. Returns True on full success.

        Regardless of outcome, the job record is always updated so the
        frontend can display what happened.
        """
        import importlib

        job_id = context.job_id
        pipeline_start = time.perf_counter()

        logger.info("[%s] Pipeline starting — %d stages", job_id, len(_STAGE_MODULES))

        # Initialize full 12-stage state so frontend inspector has immediate visibility
        stages_state: list[dict] = [
            {
                "name":        m.split(".")[-1],
                "label":       STAGE_LABELS.get(m.split(".")[-1], m.split(".")[-1]),
                "status":      "pending",
                "duration_ms": None,
                "metrics":     {},
                "warnings":    [],
                "errors":      [],
            }
            for m in _STAGE_MODULES
        ]

        # Mark job as running with stages pre-populated
        await self._job_repo.update(job_id, {
            "status": "running",
            "current_stage": "s01_upload",
            "current_stage_label": STAGE_LABELS.get("s01_upload", "Ingest"),
            "progress": 0,
            "stages": stages_state,
            "logs": [],
        })

        all_logs: list[str] = []

        for i, module_path in enumerate(_STAGE_MODULES):
            stage_key = module_path.split(".")[-1]          # e.g. "s03_scene_detect"
            stage_label = STAGE_LABELS.get(stage_key, stage_key)
            progress = int((i / len(_STAGE_MODULES)) * 100)

            logger.info("[%s] ▶ Stage %d/%d — %s",
                        job_id, i + 1, len(_STAGE_MODULES), stage_label)

            # Mark active stage as running in the 12-stage list
            stages_state[i]["status"] = "running"
            await self._job_repo.update(job_id, {
                "current_stage": stage_key,
                "current_stage_label": stage_label,
                "progress": progress,
                "stages": stages_state,
                "logs": all_logs,
            })

            # Import and run the stage
            stage_start = time.perf_counter()
            try:
                module = importlib.import_module(module_path)
                result: StageResult = await module.run(context)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as exc:
                logger.exception("[%s] Stage %s raised unhandled exception", job_id, stage_key)
                result = StageResult(
                    success=False,
                    stage_name=stage_key,
                    duration_ms=int((time.perf_counter() - stage_start) * 1000),
                    errors=[f"Unhandled exception in {stage_key}: {exc}"],
                )

            # ── Structured log entry ──────────────────────────────────────
            status_str = "SUCCESS" if result.success else "FAILED"
            metrics_str = " | ".join(f"{k}={v}" for k, v in (result.metrics or {}).items())
            log_line = (
                f"[{job_id}] Stage: {stage_key} | Status: {status_str} "
                f"| Duration: {result.duration_ms}ms"
                + (f" | {metrics_str}" if metrics_str else "")
            )
            logger.info(log_line)
            all_logs.append(log_line)
            for line in result.logs or []:
                all_logs.append(line)

            stages_state[i]["status"] = "success" if result.success else "failed"
            stages_state[i]["duration_ms"] = result.duration_ms
            stages_state[i]["metrics"] = result.metrics or {}
            stages_state[i]["warnings"] = result.warnings or []
            stages_state[i]["errors"] = result.errors or []

            progress_after = int(((i + 1) / len(_STAGE_MODULES)) * 100)
            await self._job_repo.update(job_id, {
                "progress": progress_after,
                "stages": stages_state,
                "logs": all_logs,
            })

            if not result.success:
                error_msg = "; ".join(result.errors) if result.errors else "Unknown error"
                logger.error("[%s] ✗ Stage %s FAILED: %s", job_id, stage_key, error_msg)
                await self._job_repo.update(job_id, {
                    "status":       "failed",
                    "progress":     progress_after,
                    "current_stage": stage_key,
                    "failed_stage": stage_key,
                    "error":        error_msg,
                    "stages":       stages_state,
                    "logs":         all_logs,
                })
                return False

        # ── All stages passed — persist events and mark complete ──────────
        total_ms = int((time.perf_counter() - pipeline_start) * 1000)
        logger.info("[%s] ✓ Pipeline complete in %.2fs", job_id, total_ms / 1000)

        # Extract events from context and store in EventRepository
        # ORC-3 FIX: Don't use `or` with lists — empty list is falsy but valid.
        # summary_events=[] means "no events kept after ranking" (correct behaviour),
        # not "summary stage not run".
        if "summary_events" in context.metadata:
            events = context.metadata["summary_events"]
        elif "events" in context.metadata:
            events = context.metadata["events"]
        else:
            events = []
        video_id = context.video_id
        event_records = []
        for evt in events:
            try:
                if hasattr(evt, "__dict__"):
                    d = {k: v for k, v in evt.__dict__.items()
                         if not k.startswith("_")}
                elif isinstance(evt, dict):
                    d = dict(evt)
                else:
                    continue
                # ORC-1 FIX: Use event_id (UUID set by Event dataclass).
                # id(evt) = memory address — not unique across runs.
                evt_id = (
                    d.get("event_id")
                    or d.get("id")
                    or str(uuid.uuid4())
                )
                d["id"] = evt_id
                d["event_id"] = evt_id
                d["video_id"] = video_id
                d["job_id"] = job_id
                event_records.append(d)
            except Exception:
                pass

        if event_records:
            await self._event_repo.create_many(event_records)
            logger.info("[%s] Stored %d events", job_id, len(event_records))

        # ── Build detected objects inventory from confirmed tracks ────────
        # This gives the UI an "Objects Seen" panel without re-running detection.
        detected_objects: dict[str, dict] = {}
        all_tracks = context.metadata.get("all_tracks", [])

        try:
            from app.model_registry.models.yolo_model import (
                COCO_DISPLAY_NAMES, COCO_CATEGORIES, WORLD_CATEGORIES, _world_category,
            )
        except ImportError:
            COCO_DISPLAY_NAMES = {}
            COCO_CATEGORIES = {}
            WORLD_CATEGORIES = {}
            def _world_category(cn): return "object"  # noqa: E731

        for track in all_tracks:
            cn = getattr(track, "class_name", None)
            if not cn:
                continue

            # ORC FILTER FIX: Discard unconfirmed tracks & single-frame false positives
            if not getattr(track, "is_confirmed", False):
                continue

            # Discard notorious COCO toy/sports hallucinations in indoor/security footage (e.g. teddy bear, sports ball)
            cn_clean = cn.lower().replace(" ", "_")
            if cn_clean in {
                "sports_ball", "teddy_bear", "frisbee", "kite",
                "baseball_bat", "baseball_glove", "skateboard", "surfboard",
                "tennis_racket", "snowboard", "skis", "bow_tie", "vase",
            }:
                continue

            obs = getattr(track, "observations", [])
            obs_cnt = getattr(track, "total_observations", len(obs))
            if obs_cnt < 3:
                continue

            avg_conf = getattr(track, "avg_confidence", 0.0)
            max_conf = max((getattr(o, "detection_confidence", 0.0) for o in obs), default=avg_conf)
            is_person = cn.lower() in ("person", "pedestrian", "man", "woman")

            # Non-person objects require higher confidence to avoid noisy COCO false positives
            if not is_person and (avg_conf < 0.35 or max_conf < 0.45):
                continue
            if is_person and max_conf < 0.25:
                continue

            cid = getattr(track, "class_id", -1)
            created_ms = getattr(track, "created_timestamp_ms", 0.0)

            if cn not in detected_objects:
                # Try COCO display name first, then prettify the class string
                display = COCO_DISPLAY_NAMES.get(cid) or cn.replace("_", " ").title()
                # Try COCO category, then YOLO-World category, then fuzzy
                category = COCO_CATEGORIES.get(cid) or _world_category(cn)
                detected_objects[cn] = {
                    "class_name":     cn,
                    "display_name":   display,
                    "class_id":       cid,
                    "category":       category,
                    "instance_count": 0,
                    "max_confidence": 0.0,
                    "first_seen_ms":  created_ms,
                }
            detected_objects[cn]["instance_count"] += 1
            detected_objects[cn]["max_confidence"] = round(max(
                detected_objects[cn]["max_confidence"], max_conf
            ), 4)
            detected_objects[cn]["first_seen_ms"] = min(
                detected_objects[cn]["first_seen_ms"], created_ms
            )

        # ORC-4 FIX: Sort by category priority then confidence (most useful first)
        _PRIORITY_CAT = {
            "people": 0, "electronics": 1, "bag": 2,
            "drinkware": 3, "documents": 4, "clothing": 5,
        }
        detected_objects_list = sorted(
            detected_objects.values(),
            key=lambda x: (
                x["class_name"] != "person",
                _PRIORITY_CAT.get(x.get("category", ""), 99),
                -x.get("max_confidence", 0),
                x.get("first_seen_ms", 0),
            ),
        )
        logger.info(
            "[%s] Detected object classes: %s",
            job_id,
            [o["display_name"] for o in detected_objects_list],
        )

        # Persist summary / export manifest
        export_manifest = context.metadata.get("export_manifest", {})

        video_meta = context.metadata.get("video_metadata", {})
        video_meta_dict = (
            video_meta if isinstance(video_meta, dict)
            else getattr(video_meta, "to_dict", lambda: {})()
        )

        from app.pipeline.summary_generator import generate_executive_summary
        summary = generate_executive_summary(
            video_id=video_id,
            job_id=job_id,
            video_meta=video_meta_dict,
            event_records=event_records,
            person_gallery=context.metadata.get("person_gallery", {}),
            track_to_label=context.metadata.get("track_to_label", {}),
            export_manifest=export_manifest,
        )
        context.metadata["summary"] = summary

        if "summary" not in export_manifest:
            export_manifest["summary"] = {}
        export_manifest["summary"]["compression_ratio"] = summary["compression_ratio"]
        export_manifest["summary"]["actors_count"] = summary["actors_count"]
        export_manifest["compression_ratio"] = summary["compression_ratio"]

        await self._job_repo.update(job_id, {
            "status":           "completed",
            "progress":         100,
            "current_stage":    "done",
            "stages":           stages_state,
            "logs":             all_logs,
            "event_count":      len(event_records),
            "summary":          summary,
            "export_manifest":  export_manifest,
            "total_duration_ms": total_ms,
            "video_metadata":   video_meta_dict,
            "detected_objects": detected_objects_list,
            # ── Phase 7: Person ReID data ───────────────────────────────────
            # person_gallery: {label → {first_seen_ms, last_seen_ms, crop_path, ...}}
            # Used by the timeline API to build the "People Detected" panel.
            "person_gallery":   context.metadata.get("person_gallery", {}),
            "track_to_label":   context.metadata.get("track_to_label", {}),
            "unique_persons":   len(set(context.metadata.get("track_to_label", {}).values())),
        })

        return True

