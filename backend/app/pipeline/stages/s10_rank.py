"""
Pipeline Stage s10: Ranking Engine — Phase 9 Implementation.

Enriches story segments with two independent score dimensions:
  importance_score — visual/domain significance (computed here)
  narrative_score  — story coherence value (from Phase 8, preserved)

Both scores are stored independently so the compression policy can
use them with configurable weights — supporting the evaluation benchmark
that the mentor recommended: "measure precision/recall for each strategy."
"""

import logging
import time

from app.engines.temporal.ranking_engine.config import RankingConfig
from app.engines.temporal.ranking_engine.ranker import RankingEngine
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s10_rank"


async def run(context: PipelineContext) -> StageResult:
    """
    Rank story segments by importance + narrative value.

    Reads from context:
        metadata["story_segments"]   — list[StorySegment] from s09
        metadata["motion_profiles"]  — dict[track_id, MotionProfile] from s06

    Writes to context:
        metadata["ranking_result"]   — RankingResult
        metadata["ranked_segments"]  — list[RankedSegment] (sorted desc by combined_rank)
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting ranking for job {context.job_id}")

    # ── Step 1: Read inputs ────────────────────────────────────────────────
    story_segments = context.metadata.get("story_segments")
    if story_segments is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False, stage_name=STAGE_NAME, duration_ms=duration_ms,
            errors=["story_segments not in context — s09_story_build must run first"],
            logs=logs,
        )

    motion_profiles = context.metadata.get("motion_profiles", {})
    logs.append(f"[{STAGE_NAME}] {len(story_segments)} segments to rank")

    if not story_segments:
        context.metadata["ranking_result"] = None
        context.metadata["ranked_segments"] = []
        duration_ms = int((time.perf_counter() - start) * 1000)
        save_stage_metrics(context.job_id, STAGE_NAME, {"total_ranked": 0})
        return StageResult(
            success=True, stage_name=STAGE_NAME, duration_ms=duration_ms,
            warnings=["No story segments to rank."], errors=[],
            metrics={"total_ranked": 0}, logs=logs,
        )

    # ── Step 2: Configure ranker ───────────────────────────────────────────
    try:
        config = RankingConfig(
            w_importance=float(context.settings.get("rank_w_importance", 0.40)),
            w_narrative=float(context.settings.get("rank_w_narrative", 0.60)),
            max_motion_intensity=float(context.settings.get("rank_max_motion", 0.05)),
        )
    except ValueError as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False, stage_name=STAGE_NAME, duration_ms=duration_ms,
            errors=[f"RankingConfig error: {e}"], logs=logs,
        )

    # ── Step 3: Rank ───────────────────────────────────────────────────────
    engine = RankingEngine(config=config)
    result = engine.rank(story_segments, motion_profiles)

    # ── Step 4: Store ──────────────────────────────────────────────────────
    context.metadata["ranking_result"] = result
    context.metadata["ranked_segments"] = result.ranked_segments

    # ── Step 5: Warnings ───────────────────────────────────────────────────
    if result.ranked_segments:
        top = result.ranked_segments[0]
        logs.append(
            f"[{STAGE_NAME}] Rank 1: segment {top.segment.segment_id} "
            f"(combined={top.combined_rank:.4f}, "
            f"importance={top.importance_score:.4f}, "
            f"narrative={top.narrative_score:.4f})"
        )

    # ── Step 6: Metrics ────────────────────────────────────────────────────
    metrics = result.to_metrics_dict()
    metrics["w_importance"] = config.w_importance
    metrics["w_narrative"] = config.w_narrative
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

    return StageResult(
        success=True, stage_name=STAGE_NAME, duration_ms=duration_ms,
        warnings=warnings, errors=[], metrics=metrics, logs=logs,
    )
