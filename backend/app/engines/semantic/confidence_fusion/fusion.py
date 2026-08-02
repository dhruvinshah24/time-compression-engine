"""
Confidence Fusion Engine — Semantic Intelligence Engine, Phase 7.

Combines five independent confidence signals into a single fused score
for each event. The five dimensions are preserved in a ConfidenceVector,
so downstream stages can inspect and experiment with different fusion strategies.

Why multi-dimensional instead of a single average:
  Different signals have different failure modes:
  - Detection confidence drops in low light.
  - Motion confidence drops for short tracks.
  - Rule confidence is a static prior independent of input quality.
  - Track stability drops when objects are frequently occluded.
  - Scene reliability drops during camera motion.

  Keeping them separate lets Phase 10 (Evaluation) identify which signal
  is most predictive on each benchmark video, and adjust weights accordingly.
  A single average would discard this diagnostic information.

Output:
  Each Event is enriched with a ConfidenceVector (all 5 dimensions + fused score).
  Events below min_fused_confidence are filtered out.
  The FusionResult exposes calibration statistics for the evaluation chapter.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.semantic.confidence_fusion.config import FusionConfig
from app.engines.semantic.event_understanding.engine import Event, EventUnderstandingResult
from app.engines.semantic.event_understanding.rules import KNOWLEDGE_BASE
from app.engines.perception.tracker.track import Track
from app.engines.perception.motion_analyzer.analyzer import MotionProfile
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ConfidenceVector — the 5-dimensional confidence representation
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceVector:
    """
    Five-dimensional confidence for a single event.

    Each dimension is independent and interpretable.
    Together they form the fused confidence used by Phase 8 (Story Preservation).

    detection:      How confident was the object detector? (from track.avg_confidence)
    motion:         How reliable is the motion analysis? (from motion_profile.motion_confidence)
    rule:           How specific/reliable is the rule that fired? (from rule.rule_confidence)
    track_stability: How long and consistent was the track? (derived from track history)
    scene_reliability: How clean was the scene? (camera motion, frame quality)

    fused:          Weighted combination per FusionConfig strategy.
    weights_used:   The exact weights applied — for reproducibility.
    """
    detection: float
    motion: float
    rule: float
    track_stability: float
    scene_reliability: float
    fused: float
    weights_used: dict[str, float] = field(default_factory=dict)
    strategy_used: str = "weighted_linear"

    def to_dict(self) -> dict:
        components = {
            "detection": round(self.detection, 4),
            "motion": round(self.motion, 4),
            "rule": round(self.rule, 4),
            "track_stability": round(self.track_stability, 4),
            "scene_reliability": round(self.scene_reliability, 4),
        }
        return {
            "fused": round(self.fused, 4),
            "components": components,
            # Flat access retained for backward compatibility + easier inspection
            "detection": round(self.detection, 4),
            "motion": round(self.motion, 4),
            "rule": round(self.rule, 4),
            "track_stability": round(self.track_stability, 4),
            "scene_reliability": round(self.scene_reliability, 4),
            "weights_used": {k: round(v, 4) for k, v in self.weights_used.items()},
            "strategy": self.strategy_used,
        }

    @property
    def weakest_dimension(self) -> str:
        """Returns the name of the lowest-scoring dimension — useful for debugging."""
        dims = {
            "detection": self.detection,
            "motion": self.motion,
            "rule": self.rule,
            "track_stability": self.track_stability,
            "scene_reliability": self.scene_reliability,
        }
        return min(dims, key=dims.get)

    @property
    def strongest_dimension(self) -> str:
        dims = {
            "detection": self.detection,
            "motion": self.motion,
            "rule": self.rule,
            "track_stability": self.track_stability,
            "scene_reliability": self.scene_reliability,
        }
        return max(dims, key=dims.get)


# ---------------------------------------------------------------------------
# FusionResult
# ---------------------------------------------------------------------------

@dataclass
class FusionResult:
    """Output of the confidence fusion stage."""
    fused_events: list[Event]             # events with confidence_vector populated
    discarded_events: list[Event]         # filtered out by min_fused_confidence
    confidence_vectors: dict[str, ConfidenceVector]  # event_id → vector

    @property
    def total_fused(self) -> int:
        return len(self.fused_events)

    @property
    def total_discarded(self) -> int:
        return len(self.discarded_events)

    def to_metrics_dict(self) -> dict:
        if not self.fused_events:
            return {
                "total_fused": 0,
                "total_discarded": self.total_discarded,
                "avg_fused_confidence": 0.0,
                "min_fused_confidence": 0.0,
                "max_fused_confidence": 0.0,
                "dimension_means": {},
            }

        confidences = [v.fused for v in self.confidence_vectors.values()
                       if v.fused > 0]

        dim_means = {}
        for dim in ["detection", "motion", "rule", "track_stability", "scene_reliability"]:
            values = [getattr(v, dim) for v in self.confidence_vectors.values()]
            dim_means[dim] = round(float(np.mean(values)), 4) if values else 0.0

        return {
            "total_fused": self.total_fused,
            "total_discarded": self.total_discarded,
            "avg_fused_confidence": round(float(np.mean(confidences)), 4) if confidences else 0.0,
            "min_fused_confidence": round(float(np.min(confidences)), 4) if confidences else 0.0,
            "max_fused_confidence": round(float(np.max(confidences)), 4) if confidences else 0.0,
            "dimension_means": dim_means,
        }


# ---------------------------------------------------------------------------
# ConfidenceFuser
# ---------------------------------------------------------------------------

# Build rule_confidence lookup from knowledge base
_RULE_CONFIDENCE_MAP: dict[str, float] = {
    rule.name: rule.rule_confidence for rule in KNOWLEDGE_BASE
}


class ConfidenceFuser(IntelligenceModule):
    """
    Fuses five independent confidence signals into a single score per event.

    Belongs to: Semantic Intelligence Engine
    Phase: 7 (implemented)

    Input:  EventUnderstandingResult (from Phase 6)
            Track list + MotionProfiles (from Phase 5)
            Camera motion frames (from Phase 5)
    Output: FusionResult — events with enriched ConfidenceVector
    """

    name = "ConfidenceFuser"
    version = "0.7.0"
    engine = "Semantic Intelligence Engine"

    def __init__(self, config: FusionConfig | None = None) -> None:
        self.config = config or FusionConfig()
        self._calls_total = 0
        self._total_duration_ms = 0

    def fuse(
        self,
        events: list[Event],
        tracks: dict[int, Track],           # track_id → Track
        motion_profiles: dict[int, MotionProfile],
        camera_motion_frames: list[int] | None = None,
    ) -> FusionResult:
        """
        Enrich each event with a ConfidenceVector and filter by fused threshold.

        Args:
            events:               Events from Phase 6.
            tracks:               dict[track_id → Track] for stability computation.
            motion_profiles:      dict[track_id → MotionProfile] from Phase 5.
            camera_motion_frames: Frame numbers dominated by camera motion.

        Returns:
            FusionResult with fused_events and discarded_events.
        """
        self._calls_total += 1
        start = time.perf_counter()

        camera_frames: set[int] = set(camera_motion_frames or [])
        cfg = self.config

        fused_events: list[Event] = []
        discarded_events: list[Event] = []
        confidence_vectors: dict[str, ConfidenceVector] = {}

        for event in events:
            track = tracks.get(event.track_id)
            profile = motion_profiles.get(event.track_id)

            vec = self._compute_vector(event, track, profile, camera_frames)
            confidence_vectors[event.event_id] = vec

            # Update event confidence with fused value
            event.confidence = vec.fused
            # Attach vector to evidence for full auditability
            event.evidence["confidence_vector"] = vec.to_dict()

            if vec.fused >= cfg.min_fused_confidence:
                fused_events.append(event)
            else:
                discarded_events.append(event)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._total_duration_ms += elapsed_ms

        logger.info(
            "ConfidenceFuser: %d events fused, %d discarded (threshold=%.2f) in %dms",
            len(fused_events), len(discarded_events), cfg.min_fused_confidence, elapsed_ms,
        )

        return FusionResult(
            fused_events=fused_events,
            discarded_events=discarded_events,
            confidence_vectors=confidence_vectors,
        )

    def _compute_vector(
        self,
        event: Event,
        track: Track | None,
        profile: MotionProfile | None,
        camera_frames: set[int],
    ) -> ConfidenceVector:
        cfg = self.config

        # ── Dimension 1: Detection confidence ─────────────────────────────
        d_detection = track.avg_confidence if track else event.confidence

        # ── Dimension 2: Motion confidence ────────────────────────────────
        d_motion = profile.motion_confidence if profile else 0.5

        # ── Dimension 3: Rule confidence ──────────────────────────────────
        d_rule = _RULE_CONFIDENCE_MAP.get(event.rule_name, 0.75)

        # ── Dimension 4: Track stability ──────────────────────────────────
        # "How continuously was this track matched?"
        # Proxy: matched frames relative to full_stability_frames
        if track is not None:
            d_track_stability = min(
                track.total_frames_matched / cfg.full_stability_frames, 1.0
            )
        else:
            d_track_stability = 0.5

        # ── Dimension 5: Scene reliability ────────────────────────────────
        # "What fraction of the event's frames were camera-motion-dominated?"
        if camera_frames:
            event_frames = set(range(event.start_frame, event.end_frame + 1))
            if event_frames:
                overlap_fraction = len(event_frames & camera_frames) / len(event_frames)
                # Linear penalty: 0% overlap → 1.0; full_penalty_fraction → 0.0
                penalty = min(
                    overlap_fraction / cfg.camera_motion_full_penalty_fraction, 1.0
                )
                d_scene_reliability = 1.0 - (0.6 * penalty)  # max penalty = 60% reduction
            else:
                d_scene_reliability = 1.0
        else:
            d_scene_reliability = 1.0

        # ── Fusion ─────────────────────────────────────────────────────────
        fused = self._fuse(
            d_detection, d_motion, d_rule, d_track_stability, d_scene_reliability
        )

        weights = {
            "detection": cfg.w_detection,
            "motion": cfg.w_motion,
            "rule": cfg.w_rule,
            "track_stability": cfg.w_track_stability,
            "scene_reliability": cfg.w_scene_reliability,
        }

        return ConfidenceVector(
            detection=round(d_detection, 4),
            motion=round(d_motion, 4),
            rule=round(d_rule, 4),
            track_stability=round(d_track_stability, 4),
            scene_reliability=round(d_scene_reliability, 4),
            fused=round(fused, 4),
            weights_used=weights,
            strategy_used=cfg.fusion_strategy,
        )

    def _fuse(
        self,
        detection: float, motion: float, rule: float,
        track_stability: float, scene_reliability: float,
    ) -> float:
        cfg = self.config
        values = [detection, motion, rule, track_stability, scene_reliability]
        weights = [
            cfg.w_detection, cfg.w_motion, cfg.w_rule,
            cfg.w_track_stability, cfg.w_scene_reliability,
        ]

        if cfg.fusion_strategy == "weighted_linear":
            return float(np.clip(sum(v * w for v, w in zip(values, weights)), 0.0, 1.0))

        elif cfg.fusion_strategy == "geometric":
            # Weighted geometric mean: product of v^w
            # More sensitive to very low individual dimensions
            result = 1.0
            for v, w in zip(values, weights):
                result *= max(v, 1e-6) ** w
            return float(np.clip(result, 0.0, 1.0))

        elif cfg.fusion_strategy == "harmonic":
            # Weighted harmonic mean
            denom = sum(w / max(v, 1e-6) for v, w in zip(values, weights))
            return float(np.clip(1.0 / denom if denom > 0 else 0.0, 0.0, 1.0))

        elif cfg.fusion_strategy == "min":
            # Min-component: overall confidence is limited by weakest signal
            return float(min(values))

        else:
            raise ValueError(f"Unknown fusion_strategy: {cfg.fusion_strategy!r}. "
                             f"Use: weighted_linear | geometric | harmonic | min")

    async def process(self, context: PipelineContext) -> StageResult:
        from app.pipeline.stages import s08_confidence_fuse
        return await s08_confidence_fuse.run(context)

    def health_check(self) -> ModuleHealth:
        return ModuleHealth.READY

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
