"""
Compression Policy — Temporal Engine, Phase 9.

Makes the final keep/discard decision for each event in the video.

Design principles (per mentor guidance):

1. Rank chains as atomic units, not individual events.
   "Entry → Walk → Pickup → Exit should survive or disappear as a unit
   unless there's a compelling reason to split it."
   This prevents narrative fragmentation — a common failure mode of
   simple confidence-threshold approaches.

2. Preserve narrative coherence first, trim importance second.
   If we must discard to hit the target ratio, we discard by combined_rank
   (low importance AND low narrative value). We never discard a COMPLETE arc
   with high narrative_score to make room for an isolated high-importance event.

3. Every decision is documented.
   CompressionDecision.reason explains exactly why an event was kept or discarded.
   This feeds back into the explainability layer.

Evaluation metrics produced (per mentor recommendation):
  - story_completeness_retained: fraction of COMPLETE segments kept
  - broken_narratives: segments where some events kept and some discarded
  - avg_narrative_chain_length: mean events per kept chain
  - compression_ratio_achieved: actual ratio vs target

These metrics go directly into the Phase 9 report and evaluation chapter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from app.engines.temporal.compression_policy.config import CompressionConfig
from app.engines.temporal.ranking_engine.ranker import RankedSegment, RankingResult
from app.engines.temporal.story_preservation.story_builder import (
    StoryCompleteness,
    StorySegment,
)
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CompressionDecision
# ---------------------------------------------------------------------------

@dataclass
class CompressionDecision:
    """
    Keep/discard decision for a single event.

    reason: human-readable explanation of the decision. One of:
      "complete_chain_preserved"  — part of a COMPLETE arc (always_keep_complete)
      "high_combined_rank"        — survived target ratio cut
      "below_ratio_threshold"     — discarded to meet target ratio
      "low_narrative_quality"     — below completeness_min_threshold
    """
    event_id: str
    segment_id: str
    keep: bool
    importance_score: float
    narrative_score: float
    combined_score: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "segment_id": self.segment_id,
            "keep": self.keep,
            "importance_score": round(self.importance_score, 4),
            "narrative_score": round(self.narrative_score, 4),
            "combined_score": round(self.combined_score, 4),
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# CompressionResult
# ---------------------------------------------------------------------------

@dataclass
class CompressionResult:
    """
    Output of the Compression Policy.

    decisions:          One decision per event (complete audit trail).
    kept_events:        Events that survived the compression.
    discarded_events:   Events that were removed.
    kept_segments:      Story segments with at least one kept event.
    """
    decisions: list[CompressionDecision] = field(default_factory=list)
    kept_event_ids: set[str] = field(default_factory=set)
    discarded_event_ids: set[str] = field(default_factory=set)
    kept_segment_ids: set[str] = field(default_factory=set)
    discarded_segment_ids: set[str] = field(default_factory=set)

    @property
    def total_events(self) -> int:
        return len(self.kept_event_ids) + len(self.discarded_event_ids)

    @property
    def compression_ratio_achieved(self) -> float:
        if self.total_events == 0:
            return 0.0
        return len(self.kept_event_ids) / self.total_events

    def to_metrics_dict(
        self,
        ranked_segments: list[RankedSegment],
    ) -> dict:
        """
        Compute evaluation metrics for the Phase 9 report and evaluation chapter.

        Metrics per mentor recommendation:
          - story_completeness_retained
          - broken_narratives
          - avg_narrative_chain_length
          - graph_connectivity_retained (edges_preserved / total_edges)
        """
        # Story completeness retained
        complete_segs = [
            rs for rs in ranked_segments
            if rs.segment.completeness == StoryCompleteness.COMPLETE
        ]
        complete_kept = sum(
            1 for rs in complete_segs
            if rs.segment.segment_id in self.kept_segment_ids
        )
        completeness_retained = (
            complete_kept / len(complete_segs) if complete_segs else 1.0
        )

        # Broken narratives: segments where chain_atomicity was violated
        # (should be 0 if chain_atomicity=True)
        broken = 0
        for rs in ranked_segments:
            seg_events = {e.event_id for e in rs.segment.events}
            kept_in_seg = seg_events & self.kept_event_ids
            if 0 < len(kept_in_seg) < len(seg_events):
                broken += 1

        # Average narrative chain length (events per kept segment)
        kept_seg_lengths = [
            rs.segment.event_count
            for rs in ranked_segments
            if rs.segment.segment_id in self.kept_segment_ids
        ]
        avg_chain_length = float(np.mean(kept_seg_lengths)) if kept_seg_lengths else 0.0

        return {
            "total_events": self.total_events,
            "kept_events": len(self.kept_event_ids),
            "discarded_events": len(self.discarded_event_ids),
            "compression_ratio_achieved": round(self.compression_ratio_achieved, 4),
            "kept_segments": len(self.kept_segment_ids),
            "discarded_segments": len(self.discarded_segment_ids),
            "story_completeness_retained": round(completeness_retained, 4),
            "broken_narratives": broken,
            "avg_narrative_chain_length": round(avg_chain_length, 4),
        }


# ---------------------------------------------------------------------------
# CompressionPolicy
# ---------------------------------------------------------------------------

class CompressionPolicy:
    """
    Makes keep/discard decisions for all events using ranked story segments.

    Algorithm:
      1. Discard segments below completeness_min_threshold immediately.
      2. If always_keep_complete: mark all COMPLETE arcs as kept.
      3. From remaining segments, apply target_ratio cut by combined_rank.
      4. With chain_atomicity=True: keep/discard all events in a segment together.
      5. Record CompressionDecision for every event with reason.
    """

    def __init__(self, config: CompressionConfig | None = None) -> None:
        self.config = config or CompressionConfig()

    def apply(self, ranking_result: RankingResult) -> CompressionResult:
        """
        Apply compression policy to the ranking result.

        Args:
            ranking_result: Output of RankingEngine with ranked segments.

        Returns:
            CompressionResult with decisions for every event.
        """
        cfg = self.config
        ranked = ranking_result.ranked_segments

        decisions: list[CompressionDecision] = []
        kept_event_ids: set[str] = set()
        discarded_event_ids: set[str] = set()
        kept_segment_ids: set[str] = set()
        discarded_segment_ids: set[str] = set()

        # ── Step 1: Partition segments into definite keep / candidate / discard
        definite_keep: list[RankedSegment] = []
        candidates: list[RankedSegment] = []
        definite_discard: list[RankedSegment] = []

        for rs in ranked:
            if rs.narrative_score < cfg.completeness_min_threshold:
                definite_discard.append(rs)
            elif cfg.always_keep_complete and rs.segment.completeness == StoryCompleteness.COMPLETE:
                definite_keep.append(rs)
            else:
                candidates.append(rs)

        # ── Step 2: Apply target_ratio cut on candidates ──────────────────
        # Count events already committed to keep
        events_kept_so_far = sum(rs.segment.event_count for rs in definite_keep)
        total_events = sum(rs.segment.event_count for rs in ranked)
        target_keep = int(total_events * cfg.target_ratio)
        budget_remaining = max(0, target_keep - events_kept_so_far)

        # candidates are already sorted by combined_rank desc (from RankingEngine)
        candidate_keep: list[RankedSegment] = []
        candidate_discard: list[RankedSegment] = []

        for rs in candidates:
            if cfg.chain_atomicity:
                # Keep entire segment or none
                if rs.segment.event_count <= budget_remaining:
                    candidate_keep.append(rs)
                    budget_remaining -= rs.segment.event_count
                else:
                    candidate_discard.append(rs)
            else:
                if budget_remaining > 0:
                    candidate_keep.append(rs)
                    budget_remaining -= rs.segment.event_count
                else:
                    candidate_discard.append(rs)

        # ── Step 3: Build decisions ────────────────────────────────────────
        for rs in definite_keep:
            reason = "complete_chain_preserved"
            self._record_segment(
                rs, keep=True, reason=reason,
                decisions=decisions,
                kept_event_ids=kept_event_ids,
                kept_segment_ids=kept_segment_ids,
                ranking_result=ranking_result,
            )

        for rs in candidate_keep:
            self._record_segment(
                rs, keep=True, reason="high_combined_rank",
                decisions=decisions,
                kept_event_ids=kept_event_ids,
                kept_segment_ids=kept_segment_ids,
                ranking_result=ranking_result,
            )

        for rs in candidate_discard:
            self._record_segment(
                rs, keep=False, reason="below_ratio_threshold",
                decisions=decisions,
                kept_event_ids=discarded_event_ids,
                kept_segment_ids=discarded_segment_ids,
                ranking_result=ranking_result,
            )

        for rs in definite_discard:
            self._record_segment(
                rs, keep=False, reason="low_narrative_quality",
                decisions=decisions,
                kept_event_ids=discarded_event_ids,
                kept_segment_ids=discarded_segment_ids,
                ranking_result=ranking_result,
            )

        return CompressionResult(
            decisions=decisions,
            kept_event_ids=kept_event_ids,
            discarded_event_ids=discarded_event_ids,
            kept_segment_ids=kept_segment_ids,
            discarded_segment_ids=discarded_segment_ids,
        )

    def _record_segment(
        self,
        rs: RankedSegment,
        keep: bool,
        reason: str,
        decisions: list[CompressionDecision],
        kept_event_ids: set[str],
        kept_segment_ids: set[str],
        ranking_result: RankingResult,
    ) -> None:
        # Always record the segment_id in whichever set was passed
        # (caller passes kept_segment_ids or discarded_segment_ids appropriately)
        kept_segment_ids.add(rs.segment.segment_id)
        for event in rs.segment.events:
            imp_score = ranking_result.event_importance.get(event.event_id)
            decisions.append(CompressionDecision(
                event_id=event.event_id,
                segment_id=rs.segment.segment_id,
                keep=keep,
                importance_score=imp_score.combined if imp_score else 0.5,
                narrative_score=rs.narrative_score,
                combined_score=rs.combined_rank,
                reason=reason,
            ))
            kept_event_ids.add(event.event_id)
