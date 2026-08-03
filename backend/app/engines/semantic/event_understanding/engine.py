"""
Event Understanding Engine — Semantic Intelligence Engine, Phase 6.

Answers: "What happened?" rather than "What is visible?"

This is the first stage that interprets perception outputs into
human-meaningful events. Every event is traceable back to the
specific track, motion profile, and rule that produced it —
which is the explainability guarantee.

Architecture:
  Rules (knowledge base) → Evaluator → Events
                          ↑
              (no model weights, pure logic)

The engine is deliberately rule-based for Phase 6:
  1. Easy to understand and debug.
  2. Every event has a documented reason.
  3. New domain knowledge is added by editing rules.py, not retraining.

Hybrid reasoning (rules + LLM) is planned for Phase 9 in hybrid_reasoner.py.
The interface here does not change when that upgrade is made.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.perception.motion_analyzer.analyzer import MotionProfile
from app.engines.perception.tracker.track import Track, TrackState
from app.engines.semantic.event_understanding.config import EventUnderstandingConfig
from app.engines.semantic.event_understanding.rules import (
    KNOWLEDGE_BASE,
    EventRule,
    EventType,
)
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event data class
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """
    A single semantic event detected in the video.

    Every field is populated — there are no optional or unknown fields.
    This is the contract that Phase 8 (Event Graph) depends on.

    event_id:    UUID string — globally unique per event.
    event_type:  One of the EventType constants (e.g. "person_walking").
    track_id:    Which track produced this event.
    class_name:  Object class (from the track).
    rule_name:   Which rule in the knowledge base fired.
    confidence:  [0.0, 1.0] event confidence from the rule evaluator.
    evidence:    Human-readable dict explaining why this event fired.
                 This is the explainability output — cite-able in a viva.

    start_frame / end_frame: Temporal span (from the track's observation window).
    start_ms / end_ms:       Same, in milliseconds.
    """
    event_id: str
    event_type: str
    track_id: int
    class_name: str
    rule_name: str
    confidence: float
    evidence: dict
    start_frame: int
    end_frame: int
    start_ms: float
    end_ms: float

    # Explicit provenance chain — answers "why was this event generated?"
    # Format: ["track_<id>", "motion_profile_<id>", "rule_<name>"]
    # Enables full audit tracing from event back through the pipeline.
    dependencies: list = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "track_id": self.track_id,
            "class_name": self.class_name,
            "rule_name": self.rule_name,
            "confidence": self.confidence,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "evidence": self.evidence,
            "dependencies": self.dependencies,
        }


@dataclass
class EventUnderstandingResult:
    """All events detected in a video."""
    events: list[Event] = field(default_factory=list)
    total_events: int = 0
    tracks_analyzed: int = 0
    rules_evaluated: int = 0
    camera_motion_frames_skipped: int = 0

    def events_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.events:
            counts[e.event_type] = counts.get(e.event_type, 0) + 1
        return counts

    def events_by_track(self) -> dict[int, list[Event]]:
        by_track: dict[int, list[Event]] = {}
        for e in self.events:
            by_track.setdefault(e.track_id, []).append(e)
        return by_track

    def to_metrics_dict(self) -> dict:
        return {
            "total_events": self.total_events,
            "tracks_analyzed": self.tracks_analyzed,
            "rules_evaluated": self.rules_evaluated,
            "camera_motion_frames_skipped": self.camera_motion_frames_skipped,
            "events_by_type": self.events_by_type(),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class EventUnderstandingEngine(IntelligenceModule):
    """
    Rule-based semantic event understanding.

    Belongs to: Semantic Intelligence Engine
    Phase: 6 (implemented)

    For each confirmed track, evaluates all rules in the knowledge base.
    Generates an Event for every rule that matches.

    Camera-motion-dominated frames are optionally suppressed (configurable).
    """

    name = "EventUnderstandingEngine"
    version = "0.6.0"
    engine = "Semantic Intelligence Engine"

    def __init__(
        self,
        config: EventUnderstandingConfig | None = None,
        rules: list[EventRule] | None = None,
    ) -> None:
        self.config = config or EventUnderstandingConfig()
        self.rules = rules if rules is not None else list(KNOWLEDGE_BASE)
        self._calls_total = 0
        self._total_duration_ms = 0

    def understand(
        self,
        tracks: list[Track],
        motion_profiles: dict[int, MotionProfile],
        camera_motion_frames: list[int] | None = None,
    ) -> EventUnderstandingResult:
        """
        Evaluate all rules against all confirmed tracks.

        Args:
            tracks:               All tracks (confirmed + ended).
            motion_profiles:      dict[track_id → MotionProfile] from Phase 5.
            camera_motion_frames: Frame numbers dominated by camera motion (suppress events).

        Returns:
            EventUnderstandingResult with all detected events.
        """
        self._calls_total += 1
        start = time.perf_counter()

        camera_frames: set[int] = set(camera_motion_frames or [])
        # finalize() moves all tracks to ENDED, so is_confirmed (ACTIVE|LOST) is always
        # False by the time the engine runs. Use confirmed_at_frame as the authoritative
        # marker — if it was set, the track was genuinely confirmed during tracking.
        confirmed_tracks = [
            t for t in tracks
            if t.confirmed_at_frame is not None or t.is_confirmed
        ]
        new_track_ids: set[int] = set()  # tracks that are "newly confirmed" this pass
        ended_track_ids: set[int] = set(
            t.track_id for t in tracks if t.state == TrackState.ENDED
        )

        # Tracks with >= min_track_frames are considered "new confirmed" entries
        for t in confirmed_tracks:
            if t.total_frames_matched >= self.config.min_track_frames_for_entry:
                new_track_ids.add(t.track_id)

        events: list[Event] = []
        rules_evaluated = 0
        camera_skipped = 0

        for track in confirmed_tracks:
            profile = motion_profiles.get(track.track_id)

            # Skip tracks whose observations fall entirely in camera-motion frames
            if camera_frames and self.config.suppress_camera_motion_events:
                track_frames = {o.frame_number for o in track.observations}
                if track_frames and track_frames.issubset(camera_frames):
                    camera_skipped += 1
                    continue

            ctx = {
                "is_new": track.track_id in new_track_ids,
                "is_ended": track.track_id in ended_track_ids,
            }

            for rule in self.rules:
                rules_evaluated += 1
                matched, confidence, evidence = rule.evaluate(track, profile, ctx)

                if not matched:
                    continue

                if confidence < self.config.min_event_confidence:
                    continue

                # Build explicit provenance chain
                deps = [f"track_{track.track_id}", f"rule_{rule.name}"]
                if profile is not None:
                    deps.append(f"motion_profile_{track.track_id}")

                event = Event(
                    event_id=str(uuid.uuid4()),
                    event_type=rule.event_type,
                    track_id=track.track_id,
                    class_name=track.class_name,
                    rule_name=rule.name,
                    confidence=confidence,
                    evidence=evidence,
                    start_frame=track.created_frame,
                    end_frame=track.last_seen_frame,
                    start_ms=track.created_timestamp_ms,
                    end_ms=track.last_seen_timestamp_ms,
                    dependencies=deps,
                )
                events.append(event)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._total_duration_ms += elapsed_ms

        result = EventUnderstandingResult(
            events=events,
            total_events=len(events),
            tracks_analyzed=len(confirmed_tracks),
            rules_evaluated=rules_evaluated,
            camera_motion_frames_skipped=camera_skipped,
        )

        logger.info(
            "EventUnderstanding: %d events from %d tracks "
            "(%d rules × %d tracks = %d evaluations) in %dms",
            len(events), len(confirmed_tracks),
            len(self.rules), len(confirmed_tracks), rules_evaluated,
            elapsed_ms,
        )
        return result

    async def process(self, context: PipelineContext) -> StageResult:
        from app.pipeline.stages import s07_event_understand
        return await s07_event_understand.run(context)

    def health_check(self) -> ModuleHealth:
        return ModuleHealth.READY  # pure Python — always available

    def get_metrics(self) -> ModuleMetrics:
        return ModuleMetrics(
            name=self.name,
            version=self.version,
            engine=self.engine,
            calls_total=self._calls_total,
            avg_duration_ms=(
                self._total_duration_ms / self._calls_total
                if self._calls_total > 0 else 0.0
            ),
            last_health=self.health_check(),
        )
