"""
Ranking Engine — Temporal Engine, Phase 9.

Assigns two independent scores to each story segment:

  importance_score  — "How visually significant is this event?"
                      Derived from: detection confidence, event rarity,
                      motion intensity, visual salience.

  narrative_score   — "How much does removing this break the story?"
                      Already computed by Phase 8 StoryBuilder.
                      Not recomputed here — just carried forward.

Why keep them separate (mentor recommendation):

  A person standing still for 5 seconds:
    importance  = 0.25  (not visually exciting)
    narrative   = 0.90  (removing it makes the next event inexplicable)

  A flashing light:
    importance  = 0.80  (visually salient)
    narrative   = 0.10  (irrelevant to the story)

  A flat combined score would obscure this distinction.
  The compression policy can use both dimensions independently.

Graph-based ranking:
  Segments are ranked as connected chains, not as individual events.
  A chain that is "Entry → Walk → Pickup → Exit" gets a single rank.
  If it survives, all events in the chain survive. This prevents narrative
  fragmentation — a common failure mode in simple highlight detection.

Output:
  list[RankedSegment] ordered by combined_rank descending.
  Each segment carries both scores and the final combined rank.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.perception.motion_analyzer.analyzer import MotionProfile, SpeedClass
from app.engines.semantic.event_understanding.engine import Event
from app.engines.temporal.ranking_engine.config import RankingConfig
from app.engines.temporal.story_preservation.story_builder import (
    StoryCompleteness,
    StorySegment,
)
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event rarity table
# ---------------------------------------------------------------------------
# Reflects how uncommon (and thus noteworthy) each event type is.
# Running is rarer and more attention-grabbing than standing.
# Manually assigned priors — can be updated from empirical corpus statistics.

EVENT_RARITY: dict[str, float] = {
    "person_running": 0.90,        # rare, high urgency
    "person_loitering": 0.80,      # suspicious, rare
    "vehicle_approaching": 0.75,
    "person_entered_scene": 0.62,
    "person_left_scene": 0.62,
    "person_walking": 0.50,        # common — medium rarity
    "vehicle_receding": 0.50,
    "object_appeared": 0.40,
    "object_disappeared": 0.40,
    "vehicle_stationary": 0.38,
    "person_standing": 0.30,       # very common — low rarity
    "scene_activity": 0.25,
}

_DEFAULT_RARITY = 0.50  # fallback for unknown event types


# ---------------------------------------------------------------------------
# ImportanceScore
# ---------------------------------------------------------------------------

@dataclass
class ImportanceScore:
    """
    The four independent components of visual importance.

    detection:   How confident was the detector? (proxy for object clarity)
    rarity:      How uncommon is this event type? (domain knowledge prior)
    motion:      How fast was the object moving? (normalized)
    salience:    How visually prominent was the object? (bbox area proxy)
    combined:    Weighted combination: the single importance_score.
    """
    detection: float
    rarity: float
    motion: float
    salience: float
    combined: float

    def to_dict(self) -> dict:
        return {
            "detection": round(self.detection, 4),
            "rarity": round(self.rarity, 4),
            "motion": round(self.motion, 4),
            "salience": round(self.salience, 4),
            "combined": round(self.combined, 4),
        }


# ---------------------------------------------------------------------------
# RankedSegment
# ---------------------------------------------------------------------------

@dataclass
class RankedSegment:
    """
    A story segment enriched with both score dimensions and a final rank.

    importance_score:  Visual/domain importance (computed by RankingEngine)
    narrative_score:   Story coherence value (from Phase 8, carried forward)
    combined_rank:     Weighted combination used for compression ordering
    rank:              1-indexed position (1 = most important)
    """
    segment: StorySegment
    importance_score: float
    narrative_score: float
    combined_rank: float
    rank: int = 0           # set after sorting all segments
    event_scores: dict[str, ImportanceScore] = field(default_factory=dict)  # event_id → score

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment.segment_id,
            "rank": self.rank,
            "combined_rank": round(self.combined_rank, 4),
            "importance_score": round(self.importance_score, 4),
            "narrative_score": round(self.narrative_score, 4),
            "completeness": self.segment.completeness.value,
            "event_count": self.segment.event_count,
            "duration_ms": self.segment.duration_ms,
        }


@dataclass
class RankingResult:
    """Output of the Ranking Engine."""
    ranked_segments: list[RankedSegment]   # sorted by combined_rank desc, rank assigned
    event_importance: dict[str, ImportanceScore]  # event_id → score

    def to_metrics_dict(self) -> dict:
        if not self.ranked_segments:
            return {"total_ranked": 0}
        imp_scores = [rs.importance_score for rs in self.ranked_segments]
        narr_scores = [rs.narrative_score for rs in self.ranked_segments]
        return {
            "total_ranked": len(self.ranked_segments),
            "avg_importance_score": round(float(np.mean(imp_scores)), 4),
            "avg_narrative_score": round(float(np.mean(narr_scores)), 4),
            "top_segment_id": self.ranked_segments[0].segment.segment_id if self.ranked_segments else None,
            "top_combined_rank": round(self.ranked_segments[0].combined_rank, 4) if self.ranked_segments else 0.0,
        }


# ---------------------------------------------------------------------------
# RankingEngine
# ---------------------------------------------------------------------------

class RankingEngine(IntelligenceModule):
    """
    Assigns importance scores to events and ranks story segments.

    Belongs to: Temporal Engine
    Phase: 9 (implemented)

    Separation of concerns:
      importance_score — computed here (visual/domain signals)
      narrative_score  — from Phase 8, unchanged (story coherence signals)

    Graph-based ranking:
      Segments are ranked as units. All events in a segment share
      the segment's rank (not individually scored for survival).
    """

    name = "RankingEngine"
    version = "0.9.0"
    engine = "Temporal Engine"

    def __init__(self, config: RankingConfig | None = None) -> None:
        self.config = config or RankingConfig()
        self._calls_total = 0
        self._total_duration_ms = 0

    def rank(
        self,
        segments: list[StorySegment],
        motion_profiles: dict[int, MotionProfile] | None = None,
    ) -> RankingResult:
        """
        Rank all story segments.

        Args:
            segments:        Story segments from Phase 8.
            motion_profiles: dict[track_id → MotionProfile] from Phase 5.
                             Used to compute motion intensity per event.

        Returns:
            RankingResult with ranked_segments (rank 1 = most important) and
            per-event ImportanceScore dict.
        """
        self._calls_total += 1
        start = time.perf_counter()
        profiles = motion_profiles or {}

        event_importance: dict[str, ImportanceScore] = {}
        ranked: list[RankedSegment] = []

        for segment in segments:
            # ── Per-event importance ──────────────────────────────────────
            seg_scores: dict[str, ImportanceScore] = {}
            for event in segment.events:
                score = self._compute_importance(event, profiles.get(event.track_id))
                seg_scores[event.event_id] = score
                event_importance[event.event_id] = score

            # ── Segment-level importance = mean of event scores ───────────
            if seg_scores:
                seg_importance = float(np.mean([s.combined for s in seg_scores.values()]))
            else:
                seg_importance = 0.0

            # ── Combined rank ─────────────────────────────────────────────
            cfg = self.config
            combined = float(np.clip(
                cfg.w_importance * seg_importance
                + cfg.w_narrative * segment.narrative_score,
                0.0, 1.0,
            ))

            ranked.append(RankedSegment(
                segment=segment,
                importance_score=round(seg_importance, 4),
                narrative_score=round(segment.narrative_score, 4),
                combined_rank=round(combined, 4),
                event_scores=seg_scores,
            ))

        # ── Sort and assign ranks ─────────────────────────────────────────
        ranked.sort(key=lambda rs: rs.combined_rank, reverse=True)
        for i, rs in enumerate(ranked):
            rs.rank = i + 1

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._total_duration_ms += elapsed_ms

        logger.info(
            "RankingEngine: %d segments ranked in %dms "
            "(top combined_rank=%.4f)",
            len(ranked), elapsed_ms,
            ranked[0].combined_rank if ranked else 0.0,
        )

        return RankingResult(ranked_segments=ranked, event_importance=event_importance)

    def _compute_importance(
        self,
        event: Event,
        profile: MotionProfile | None,
    ) -> ImportanceScore:
        """
        Compute ImportanceScore for a single event.

        Four components:
          detection  — event.confidence (already fused by Phase 7)
          rarity     — EVENT_RARITY lookup for event_type
          motion     — normalized avg_speed from motion profile
          salience   — bbox area proxy from the confidence_vector if available,
                       otherwise falls back to 0.5
        """
        # Detection: use fused confidence from Phase 7
        d_detection = float(np.clip(event.confidence, 0.0, 1.0))

        # Rarity: domain knowledge prior
        d_rarity = EVENT_RARITY.get(event.event_type, _DEFAULT_RARITY)

        # Motion intensity: normalize avg_speed by ceiling
        if profile is not None and profile.avg_speed_per_second > 0:
            d_motion = float(np.clip(
                profile.avg_speed_per_second / self.config.max_motion_intensity,
                0.0, 1.0,
            ))
        elif profile is not None and profile.is_stationary:
            d_motion = 0.0
        else:
            d_motion = 0.3  # unknown — mild default

        # Visual salience: extract from confidence_vector in evidence if available
        # Proxy: if the track's detection was high confidence → likely well-lit, large object
        cv = event.evidence.get("confidence_vector", {})
        d_salience = float(cv.get("detection", d_detection))

        # Weighted combination
        combined = float(np.clip(
            0.35 * d_detection
            + 0.35 * d_rarity
            + 0.20 * d_motion
            + 0.10 * d_salience,
            0.0, 1.0,
        ))

        return ImportanceScore(
            detection=round(d_detection, 4),
            rarity=round(d_rarity, 4),
            motion=round(d_motion, 4),
            salience=round(d_salience, 4),
            combined=round(combined, 4),
        )

    async def process(self, context: PipelineContext) -> StageResult:
        from app.pipeline.stages import s10_rank
        return await s10_rank.run(context)

    def health_check(self) -> ModuleHealth:
        return ModuleHealth.READY

    def get_metrics(self) -> ModuleMetrics:
        return ModuleMetrics(
            name=self.name, version=self.version, engine=self.engine,
            calls_total=self._calls_total,
            avg_duration_ms=(
                self._total_duration_ms / self._calls_total
                if self._calls_total > 0 else 0.0
            ),
            last_health=self.health_check(),
        )
