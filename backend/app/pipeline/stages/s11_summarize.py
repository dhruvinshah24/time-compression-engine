"""
Pipeline Stage s11: Compression Policy — Phase 9 Implementation.

Applies the compression policy to make final keep/discard decisions.

The key invariant (chain atomicity):
  Events within a story segment are kept or discarded as a unit.
  A "person entered → walking → exit" chain is never partially removed.
  This is what separates this system from a simple confidence threshold.

Evaluation metrics produced (per mentor recommendation):
  - story_completeness_retained
  - broken_narratives
  - avg_narrative_chain_length
  - compression_ratio_achieved

These are saved to stage metrics and will be the foundation of the
evaluation chapter's quantitative analysis.
"""

import logging
import time

from app.engines.temporal.compression_policy.config import CompressionConfig
from app.engines.temporal.compression_policy.policy import CompressionPolicy
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s11_summarize"


async def run(context: PipelineContext) -> StageResult:
    """
    Apply compression policy and produce the final summarized event list.

    Reads from context:
        metadata["ranking_result"]   — RankingResult from s10

    Writes to context:
        metadata["compression_result"]  — CompressionResult
        metadata["kept_event_ids"]      — set of event IDs that survived
        metadata["summary_events"]      — list of Event objects that survived
        metadata["events"]              — updated to kept events only (for s12)
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting compression policy for job {context.job_id}")

    # ── Step 1: Read inputs ────────────────────────────────────────────────
    ranking_result = context.metadata.get("ranking_result")
    if ranking_result is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False, stage_name=STAGE_NAME, duration_ms=duration_ms,
            errors=["ranking_result not in context — s10_rank must run first"],
            logs=logs,
        )

    ranked_segments = ranking_result.ranked_segments
    total_events = sum(rs.segment.event_count for rs in ranked_segments)
    logs.append(
        f"[{STAGE_NAME}] {len(ranked_segments)} ranked segments, "
        f"{total_events} total events"
    )

    # ── Step 2: Configure policy ───────────────────────────────────────────
    config = CompressionConfig(
        target_ratio=float(context.settings.get("compression_target_ratio", 0.40)),
        always_keep_complete=bool(context.settings.get("compression_keep_complete", True)),
        completeness_min_threshold=float(context.settings.get("compression_min_threshold", 0.20)),
        chain_atomicity=bool(context.settings.get("compression_chain_atomicity", True)),
    )
    logs.append(
        f"[{STAGE_NAME}] Policy: target_ratio={config.target_ratio:.0%}, "
        f"always_keep_complete={config.always_keep_complete}, "
        f"chain_atomicity={config.chain_atomicity}"
    )

    # ── Step 3: Apply policy ───────────────────────────────────────────────
    policy = CompressionPolicy(config=config)
    result = policy.apply(ranking_result)

    # ── Step 4: Extract surviving events ──────────────────────────────────
    all_events_by_id = {
        e.event_id: e
        for rs in ranked_segments
        for e in rs.segment.events
    }
    summary_events = [
        all_events_by_id[eid]
        for eid in result.kept_event_ids
        if eid in all_events_by_id
    ]
    # Sort by start time for chronological output
    summary_events.sort(key=lambda e: e.start_ms)

    # ── Step 5: Store in context ───────────────────────────────────────────
    context.metadata["compression_result"] = result
    context.metadata["kept_event_ids"] = result.kept_event_ids
    context.metadata["summary_events"] = summary_events
    context.metadata["events"] = summary_events   # s12 reads this

    # ── Step 6: Warnings ───────────────────────────────────────────────────
    if result.to_metrics_dict(ranked_segments)["broken_narratives"] > 0:
        warnings.append(
            "Some narrative chains were partially preserved. "
            "Enable chain_atomicity=True to prevent this."
        )
    if not summary_events:
        warnings.append("All events were discarded. Lower compression_target_ratio.")

    # ── Step 7: Evaluation metrics ─────────────────────────────────────────
    metrics = result.to_metrics_dict(ranked_segments)
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] Kept {len(result.kept_event_ids)}/{total_events} events "
        f"({result.compression_ratio_achieved:.0%} ratio)"
    )
    logs.append(
        f"[{STAGE_NAME}] Narrative completeness retained: "
        f"{metrics['story_completeness_retained']:.0%}"
    )
    logs.append(
        f"[{STAGE_NAME}] Broken narratives: {metrics['broken_narratives']}"
    )
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

    return StageResult(
        success=True, stage_name=STAGE_NAME, duration_ms=duration_ms,
        warnings=warnings, errors=[], metrics=metrics, logs=logs,
    )
