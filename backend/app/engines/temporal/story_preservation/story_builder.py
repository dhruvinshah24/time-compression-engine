"""
Story Builder — Temporal Engine, Phase 8.

Finds narrative chains in the event stream.

The mentor's framing:
  "Person entered → Person walking → Person picked parcel → Person exited"
  should be treated as a single narrative chain, not four independent events.

Architecture:
  1. Group events by track_id → per-actor event thread
  2. Classify each thread's completeness (entry/action/exit coverage)
  3. Score the narrative importance of each thread
  4. Find cross-track interactions (events co-occurring in time)
  5. Build StoryPreservationResult

Why track-centric grouping?
  A track is the system's representation of a real-world actor.
  All events from the same track are about the same physical object.
  Grouping by track captures the actor's arc through the scene.

StoryCompleteness taxonomy:
  COMPLETE:    entry + ≥1 action + exit   → full arc, highest value
  PARTIAL:     ≥2 events, some missing     → incomplete but meaningful
  ENTRY_ONLY:  person entered but we lost them (video truncated or occlusion)
  EXIT_ONLY:   person was already present when recording started
  MINIMAL:     single event only
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.semantic.event_understanding.engine import Event
from app.engines.semantic.event_understanding.rules import EventType
from app.engines.temporal.story_preservation.config import StoryConfig
from app.engines.temporal.story_preservation.continuity import ContinuityChecker, ContinuityReport
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)

# Entry / action / exit event type sets
_ENTRY_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_ENTERED_SCENE, EventType.OBJECT_APPEARED,
})
_EXIT_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_LEFT_SCENE, EventType.OBJECT_DISAPPEARED,
})
_ACTION_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_WALKING, EventType.PERSON_RUNNING,
    EventType.PERSON_STANDING, EventType.PERSON_LOITERING,
    EventType.VEHICLE_APPROACHING, EventType.VEHICLE_RECEDING,
    EventType.VEHICLE_STATIONARY,
})


# ---------------------------------------------------------------------------
# StoryCompleteness
# ---------------------------------------------------------------------------

class StoryCompleteness(str, Enum):
    COMPLETE = "complete"       # entry + action + exit — full arc
    PARTIAL = "partial"         # 2+ events, missing entry or exit
    ENTRY_ONLY = "entry_only"   # appeared but no further events
    EXIT_ONLY = "exit_only"     # exited without earlier events
    MINIMAL = "minimal"         # single event


_COMPLETENESS_SCORE: dict[StoryCompleteness, float] = {
    StoryCompleteness.COMPLETE: 1.0,
    StoryCompleteness.PARTIAL: 0.6,
    StoryCompleteness.ENTRY_ONLY: 0.4,
    StoryCompleteness.EXIT_ONLY: 0.4,
    StoryCompleteness.MINIMAL: 0.2,
}


# ---------------------------------------------------------------------------
# StorySegment
# ---------------------------------------------------------------------------

@dataclass
class StorySegment:
    """
    A narrative unit — one or more events that together form a coherent story arc.

    The core abstraction of Phase 8.

    narrative_score:  [0.0, 1.0] importance of this segment to the final output.
                      Computed from confidence, completeness, length, and duration.
    completeness:     Structural classification of how complete the arc is.
    is_coherent:      Whether continuity checks passed (temporal + semantic).
    continuity_issues: List of detected continuity violations.
    """
    segment_id: str
    track_ids: set[int]
    events: list[Event]                     # ordered by start_ms

    completeness: StoryCompleteness
    narrative_score: float                  # [0.0, 1.0]
    mean_confidence: float

    start_ms: float
    end_ms: float

    is_coherent: bool = True
    continuity_issues: list[str] = field(default_factory=list)
    continuity_warnings: list[str] = field(default_factory=list)

    interacting_segment_ids: list[str] = field(default_factory=list)  # co-occurring segments

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def event_types(self) -> list[str]:
        return [e.event_type for e in self.events]

    def to_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "track_ids": sorted(self.track_ids),
            "event_count": self.event_count,
            "event_types": self.event_types,
            "completeness": self.completeness.value,
            "narrative_score": round(self.narrative_score, 4),
            "mean_confidence": round(self.mean_confidence, 4),
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "is_coherent": self.is_coherent,
            "continuity_issues": self.continuity_issues,
            "interacting_segment_ids": self.interacting_segment_ids,
        }


@dataclass
class StoryPreservationResult:
    """All story segments found in the video."""
    segments: list[StorySegment] = field(default_factory=list)
    complete_segments: int = 0
    partial_segments: int = 0
    total_events_covered: int = 0

    def ranked_segments(self) -> list[StorySegment]:
        """Return segments sorted by narrative_score descending."""
        return sorted(self.segments, key=lambda s: s.narrative_score, reverse=True)

    def to_metrics_dict(self) -> dict:
        scores = [s.narrative_score for s in self.segments]
        return {
            "total_segments": len(self.segments),
            "complete_segments": self.complete_segments,
            "partial_segments": self.partial_segments,
            "total_events_covered": self.total_events_covered,
            "avg_narrative_score": round(float(np.mean(scores)), 4) if scores else 0.0,
            "max_narrative_score": round(float(np.max(scores)), 4) if scores else 0.0,
        }


# ---------------------------------------------------------------------------
# StoryBuilder
# ---------------------------------------------------------------------------

class StoryBuilder(IntelligenceModule):
    """
    Identifies narrative story arcs from the event stream.

    Belongs to: Temporal Engine
    Phase: 8 (implemented)

    Input:  Fused events (list[Event]) from Phase 7
    Output: StoryPreservationResult with ranked story segments
    """

    name = "StoryBuilder"
    version = "0.8.0"
    engine = "Temporal Engine"

    def __init__(self, config: StoryConfig | None = None) -> None:
        self.config = config or StoryConfig()
        self._checker = ContinuityChecker()
        self._calls_total = 0
        self._total_duration_ms = 0

    def build(self, events: list[Event]) -> StoryPreservationResult:
        """
        Identify story segments from fused events.

        Algorithm:
          1. Group events by track_id
          2. For each track group: classify completeness, check continuity, score
          3. Detect co-occurring segments (interactions across tracks)

        Args:
            events: Fused events from Phase 7, any order.

        Returns:
            StoryPreservationResult with all segments ranked by narrative_score.
        """
        self._calls_total += 1
        start = time.perf_counter()

        # ── Step 1: Group by track ─────────────────────────────────────────
        track_events: dict[int, list[Event]] = {}
        for event in events:
            track_events.setdefault(event.track_id, []).append(event)

        # Sort each track's events by time
        for tid in track_events:
            track_events[tid].sort(key=lambda e: e.start_ms)

        # ── Step 2: Build a segment per track ─────────────────────────────
        segments: list[StorySegment] = []
        for track_id, tevents in track_events.items():
            segment = self._build_segment(track_id, tevents)
            segments.append(segment)

        # ── Step 3: Detect interactions (co-occurrence across tracks) ──────
        self._link_co_occurring_segments(segments)

        # ── Step 4: Aggregate result ───────────────────────────────────────
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._total_duration_ms += elapsed_ms

        complete = sum(1 for s in segments if s.completeness == StoryCompleteness.COMPLETE)
        partial = sum(1 for s in segments if s.completeness == StoryCompleteness.PARTIAL)
        covered = sum(s.event_count for s in segments)

        result = StoryPreservationResult(
            segments=segments,
            complete_segments=complete,
            partial_segments=partial,
            total_events_covered=covered,
        )

        logger.info(
            "StoryBuilder: %d segments (%d complete, %d partial) from %d events in %dms",
            len(segments), complete, partial, len(events), elapsed_ms,
        )
        return result

    def _build_segment(self, track_id: int, events: list[Event]) -> StorySegment:
        """Build a StorySegment for one actor's event thread."""
        cfg = self.config
        seg_id = f"seg_{track_id}_{str(uuid.uuid4())[:8]}"

        # ── Completeness classification ────────────────────────────────────
        types = {e.event_type for e in events}
        has_entry = bool(types & _ENTRY_EVENTS)
        has_exit = bool(types & _EXIT_EVENTS)
        has_action = bool(types & _ACTION_EVENTS)

        if has_entry and has_exit and has_action:
            completeness = StoryCompleteness.COMPLETE
        elif has_entry and has_exit and not has_action:
            completeness = StoryCompleteness.PARTIAL  # entry + exit but no observed action
        elif has_entry and not has_exit and not has_action:
            completeness = StoryCompleteness.ENTRY_ONLY
        elif has_exit and not has_entry and not has_action:
            completeness = StoryCompleteness.EXIT_ONLY
        elif len(events) == 1:
            completeness = StoryCompleteness.MINIMAL
        else:
            completeness = StoryCompleteness.PARTIAL

        # ── Temporal span ──────────────────────────────────────────────────
        start_ms = min(e.start_ms for e in events)
        end_ms = max(e.end_ms for e in events)
        duration_ms = end_ms - start_ms

        # ── Continuity check ───────────────────────────────────────────────
        report: ContinuityReport = self._checker.check(seg_id, events)

        # ── Mean event confidence ──────────────────────────────────────────
        mean_conf = float(np.mean([e.confidence for e in events]))

        # ── Narrative score ────────────────────────────────────────────────
        completeness_factor = _COMPLETENESS_SCORE[completeness]
        length_factor = min(len(events) / cfg.full_length_events, 1.0)
        duration_factor = min(duration_ms / cfg.full_duration_ms, 1.0)

        # Apply continuity penalty (each issue reduces score by 10%)
        coherence_penalty = min(len(report.issues) * 0.10, 0.40)

        narrative_score = float(np.clip(
            (cfg.weight_confidence * mean_conf
             + cfg.weight_completeness * completeness_factor
             + cfg.weight_length * length_factor
             + cfg.weight_duration * duration_factor)
            * (1.0 - coherence_penalty),
            0.0, 1.0,
        ))

        return StorySegment(
            segment_id=seg_id,
            track_ids={track_id},
            events=events,
            completeness=completeness,
            narrative_score=narrative_score,
            mean_confidence=mean_conf,
            start_ms=start_ms,
            end_ms=end_ms,
            is_coherent=report.is_coherent,
            continuity_issues=report.issues,
            continuity_warnings=report.warnings,
        )

    def _link_co_occurring_segments(self, segments: list[StorySegment]) -> None:
        """
        Find pairs of segments that overlap in time (within co_occurrence_window_ms).
        Links them bidirectionally via interacting_segment_ids.

        Two segments are co-occurring if their time windows overlap or are within
        co_occurrence_window_ms of each other.
        """
        window = self.config.co_occurrence_window_ms
        for i, seg_a in enumerate(segments):
            for j, seg_b in enumerate(segments):
                if i >= j:
                    continue
                # Check time overlap with window buffer
                a_start, a_end = seg_a.start_ms - window, seg_a.end_ms + window
                b_start, b_end = seg_b.start_ms, seg_b.end_ms
                if a_start <= b_end and b_start <= a_end:
                    seg_a.interacting_segment_ids.append(seg_b.segment_id)
                    seg_b.interacting_segment_ids.append(seg_a.segment_id)

    async def process(self, context: PipelineContext) -> StageResult:
        from app.pipeline.stages import s09_story_build
        return await s09_story_build.run(context)

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
