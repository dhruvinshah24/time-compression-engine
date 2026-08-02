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
import logging
import time
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

        # Mark job as running
        await self._job_repo.update(job_id, {
            "status": "running",
            "current_stage": "s01_upload",
            "progress": 0,
            "stages": [],
            "logs": [],
        })

        completed_stages: list[dict] = []
        all_logs: list[str] = []

        for i, module_path in enumerate(_STAGE_MODULES):
            stage_key = module_path.split(".")[-1]          # e.g. "s03_scene_detect"
            stage_label = STAGE_LABELS.get(stage_key, stage_key)
            progress = int((i / len(_STAGE_MODULES)) * 100)

            logger.info("[%s] ▶ Stage %d/%d — %s",
                        job_id, i + 1, len(_STAGE_MODULES), stage_label)

            # Announce stage start in job record
            await self._job_repo.update(job_id, {
                "current_stage": stage_key,
                "current_stage_label": stage_label,
                "progress": progress,
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

            stage_record = {
                "name":        stage_key,
                "label":       stage_label,
                "status":      "success" if result.success else "failed",
                "duration_ms": result.duration_ms,
                "metrics":     result.metrics or {},
                "warnings":    result.warnings or [],
                "errors":      result.errors or [],
            }
            completed_stages.append(stage_record)

            if not result.success:
                error_msg = "; ".join(result.errors) if result.errors else "Unknown error"
                logger.error("[%s] ✗ Stage %s FAILED: %s", job_id, stage_key, error_msg)
                await self._job_repo.update(job_id, {
                    "status":       "failed",
                    "progress":     progress,
                    "current_stage": stage_key,
                    "failed_stage": stage_key,
                    "error":        error_msg,
                    "stages":       completed_stages,
                    "logs":         all_logs,
                })
                return False

        # ── All stages passed — persist events and mark complete ──────────
        total_ms = int((time.perf_counter() - pipeline_start) * 1000)
        logger.info("[%s] ✓ Pipeline complete in %.2fs", job_id, total_ms / 1000)

        # Extract events from context and store in EventRepository
        events = context.metadata.get("summary_events") or context.metadata.get("events") or []
        video_id = context.video_id
        event_records = []
        for evt in events:
            try:
                # Events are domain objects — convert to plain dict
                if hasattr(evt, "__dict__"):
                    d = {k: v for k, v in evt.__dict__.items()
                         if not k.startswith("_")}
                elif isinstance(evt, dict):
                    d = evt
                else:
                    continue
                d.setdefault("id", str(id(evt)))
                d["video_id"] = video_id
                d["job_id"] = job_id
                event_records.append(d)
            except Exception:
                pass

        if event_records:
            await self._event_repo.create_many(event_records)
            logger.info("[%s] Stored %d events", job_id, len(event_records))

        # Persist summary / export manifest
        summary = context.metadata.get("summary", {})
        export_manifest = context.metadata.get("export_manifest", {})

        await self._job_repo.update(job_id, {
            "status":          "completed",
            "progress":        100,
            "current_stage":   "done",
            "stages":          completed_stages,
            "logs":            all_logs,
            "event_count":     len(event_records),
            "summary":         summary,
            "export_manifest": export_manifest,
            "total_duration_ms": total_ms,
            "video_metadata":  context.metadata.get("video_metadata", {}) if isinstance(
                               context.metadata.get("video_metadata"), dict)
                               else getattr(context.metadata.get("video_metadata"), "to_dict", lambda: {})(),
        })

        return True
