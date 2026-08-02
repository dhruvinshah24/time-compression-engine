"""
Pipeline Stage s09: Story Preservation + Event Graph — Phase 8 Implementation.

This is the first stage that treats events as a narrative rather than an
independent list. Two outputs are produced:

1. StoryPreservationResult — actor-centric narrative segments with
   completeness classification and narrative scores.

2. EventGraph — relational structure with SAME_TRACK_TEMPORAL and
   CO_OCCURRENCE edges, enabling graph-based compression policy in Phase 9.

Success criteria (Phase 8):
  - Every event assigned to exactly one StorySegment
  - COMPLETE segments identified correctly (entry + action + exit)
  - CO_OCCURRENCE edges built between simultaneous events from different tracks
  - EventGraph hub nodes identified (most connected events)
  - Segments ranked by narrative_score for Phase 9
  - Zero crashes on empty event list
"""

import logging
import time

from app.engines.temporal.event_graph.config import EventGraphConfig
from app.engines.temporal.event_graph.graph_builder import EventGraphBuilder
from app.engines.temporal.story_preservation.config import StoryConfig
from app.engines.temporal.story_preservation.story_builder import StoryBuilder
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult
from app.utils.stage_metrics import save_stage_metrics

logger = logging.getLogger(__name__)

STAGE_NAME = "s09_story_build"


async def run(context: PipelineContext) -> StageResult:
    """
    Build story segments and event graph from fused events.

    Reads from context:
        metadata["events"]    — fused events from s08 (or s07 if fusion skipped)

    Writes to context:
        metadata["story_result"]      — StoryPreservationResult
        metadata["story_segments"]    — list of StorySegment (ranked by narrative_score)
        metadata["event_graph"]       — EventGraph
        metadata["ranked_segments"]   — segments sorted by narrative_score desc
    """
    start = time.perf_counter()
    warnings: list[str] = []
    logs: list[str] = []

    logs.append(f"[{STAGE_NAME}] Starting story preservation for job {context.job_id}")

    # ── Step 1: Read inputs ────────────────────────────────────────────────
    events = context.metadata.get("events")
    if events is None:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return StageResult(
            success=False,
            stage_name=STAGE_NAME,
            duration_ms=duration_ms,
            errors=["events not in context — s07_event_understand or s08_confidence_fuse must run first"],
            logs=logs,
        )

    logs.append(f"[{STAGE_NAME}] {len(events)} events to process")

    if not events:
        context.metadata["story_result"] = None
        context.metadata["story_segments"] = []
        context.metadata["event_graph"] = None
        context.metadata["ranked_segments"] = []
        warnings.append("No events to process — empty story result.")
        duration_ms = int((time.perf_counter() - start) * 1000)
        save_stage_metrics(context.job_id, STAGE_NAME, {"total_segments": 0})
        return StageResult(
            success=True, stage_name=STAGE_NAME, duration_ms=duration_ms,
            warnings=warnings, errors=[], metrics={"total_segments": 0}, logs=logs,
        )

    # ── Step 2: Configure engines ──────────────────────────────────────────
    story_config = StoryConfig(
        weight_confidence=float(context.settings.get("story_weight_confidence", 0.40)),
        weight_completeness=float(context.settings.get("story_weight_completeness", 0.30)),
        weight_length=float(context.settings.get("story_weight_length", 0.20)),
        weight_duration=float(context.settings.get("story_weight_duration", 0.10)),
        co_occurrence_window_ms=float(context.settings.get("story_co_occurrence_window_ms", 2000.0)),
    )

    graph_config = EventGraphConfig(
        max_co_occurrence_gap_ms=float(context.settings.get("graph_co_occurrence_gap_ms", 2000.0)),
        same_track_edge_weight=float(context.settings.get("graph_same_track_weight", 1.0)),
        co_occurrence_weight=float(context.settings.get("graph_co_occurrence_weight", 0.5)),
    )

    # ── Step 3: Build stories ──────────────────────────────────────────────
    story_builder = StoryBuilder(config=story_config)
    story_result = story_builder.build(events)

    # ── Step 4: Build event graph ──────────────────────────────────────────
    graph_builder = EventGraphBuilder(config=graph_config)
    event_graph = graph_builder.build(events)

    # ── Step 5: Store in context ───────────────────────────────────────────
    ranked = story_result.ranked_segments()
    context.metadata["story_result"] = story_result
    context.metadata["story_segments"] = story_result.segments
    context.metadata["event_graph"] = event_graph
    context.metadata["ranked_segments"] = ranked

    # ── Step 6: Warnings ───────────────────────────────────────────────────
    incoherent = [s for s in story_result.segments if not s.is_coherent]
    if incoherent:
        warnings.append(
            f"{len(incoherent)} segment(s) have continuity issues: "
            + ", ".join(s.segment_id for s in incoherent)
        )

    isolated = event_graph.isolated_nodes()
    if isolated:
        warnings.append(
            f"{len(isolated)} event(s) are isolated in the graph (no connections)."
        )

    if story_result.complete_segments == 0:
        warnings.append(
            "No COMPLETE story segments found. "
            "All events may be partial arcs (no entry+action+exit chains detected)."
        )

    # ── Step 7: Metrics ────────────────────────────────────────────────────
    story_metrics = story_result.to_metrics_dict()
    graph_metrics = event_graph.to_metrics_dict()
    metrics = {**story_metrics, "graph": graph_metrics}
    save_stage_metrics(context.job_id, STAGE_NAME, metrics)

    duration_ms = int((time.perf_counter() - start) * 1000)
    logs.append(
        f"[{STAGE_NAME}] {story_result.to_metrics_dict()['total_segments']} segments "
        f"({story_result.complete_segments} complete, {story_result.partial_segments} partial)"
    )
    logs.append(
        f"[{STAGE_NAME}] EventGraph: {event_graph.to_metrics_dict()['total_nodes']} nodes, "
        f"{event_graph.to_metrics_dict()['total_edges']} edges"
    )
    if ranked:
        logs.append(
            f"[{STAGE_NAME}] Top segment narrative_score: {ranked[0].narrative_score:.4f}"
        )
    logs.append(f"[{STAGE_NAME}] Completed in {duration_ms}ms")

    return StageResult(
        success=True, stage_name=STAGE_NAME, duration_ms=duration_ms,
        warnings=warnings, errors=[], metrics=metrics, artifacts=[], logs=logs,
    )
