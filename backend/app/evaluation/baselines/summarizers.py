"""
Baseline summarization methods for comparison against the Time Compression Engine.

Per mentor recommendation:
  "Begin evaluating against existing baselines... That will strengthen any future
   report or publication because you'll be demonstrating improvement relative to
   established approaches rather than only reporting your own results."

Three baselines implemented:

1. UniformSampler        — Keep every N-th event by time (no intelligence)
2. MotionOnlySummarizer  — Rank events by motion confidence, keep top fraction
3. SceneChangeSummarizer — Keep events at temporal boundaries (naive scene change proxy)

Each baseline returns a set of event_ids it would retain, allowing direct
comparison against the TCE's compression result using EvaluationMetrics.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.engines.semantic.event_understanding.engine import Event


@dataclass
class BaselineResult:
    """Output of any baseline summarizer."""
    baseline_name: str
    kept_event_ids: set[str]
    total_events: int
    compression_ratio: float   # actual fraction kept

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline_name,
            "kept": len(self.kept_event_ids),
            "total": self.total_events,
            "compression_ratio": round(self.compression_ratio, 4),
        }


# ---------------------------------------------------------------------------
# Baseline 1: Uniform Sampler
# ---------------------------------------------------------------------------

class UniformSampler:
    """
    Keep every ceil(1/target_ratio)-th event sorted by start time.

    This is the simplest possible baseline — no semantic or narrative awareness.
    It represents the output of a naive "sample every N seconds" approach.

    Expected weakness vs TCE:
      - Will likely cut incomplete narrative chains
      - No preference for entry/exit events (narrative anchors)
      - Random compression of COMPLETE arcs
    """

    name = "uniform_sampling"

    def summarize(
        self, events: list[Event], target_ratio: float = 0.40
    ) -> BaselineResult:
        if not events:
            return BaselineResult(self.name, set(), 0, 0.0)

        sorted_events = sorted(events, key=lambda e: e.start_ms)
        n_keep = max(1, int(len(sorted_events) * target_ratio))
        step = max(1, len(sorted_events) // n_keep)

        kept = {sorted_events[i].event_id for i in range(0, len(sorted_events), step)}
        # Trim to exactly n_keep if step landed us too many
        kept_list = list(kept)[:n_keep]

        return BaselineResult(
            baseline_name=self.name,
            kept_event_ids=set(kept_list),
            total_events=len(events),
            compression_ratio=len(kept_list) / len(events),
        )


# ---------------------------------------------------------------------------
# Baseline 2: Motion-Only Summarizer
# ---------------------------------------------------------------------------

class MotionOnlySummarizer:
    """
    Rank events by their motion confidence from the confidence_vector and
    keep the top target_ratio fraction.

    Represents a "highlight reel based on motion intensity" approach —
    commonly used in simple sports/action summarization systems.

    Expected weakness vs TCE:
      - Ignores narrative structure entirely
      - Prefers fast-moving events (may discard quiet narrative anchors)
      - A slowly-moving person entering the scene gets a low score
    """

    name = "motion_only"

    def summarize(
        self, events: list[Event], target_ratio: float = 0.40
    ) -> BaselineResult:
        if not events:
            return BaselineResult(self.name, set(), 0, 0.0)

        def _motion_score(event: Event) -> float:
            cv = event.evidence.get("confidence_vector", {})
            # Use motion dimension from confidence_vector if available
            return float(cv.get("motion", event.confidence))

        ranked = sorted(events, key=_motion_score, reverse=True)
        n_keep = max(1, int(len(ranked) * target_ratio))
        kept = {e.event_id for e in ranked[:n_keep]}

        return BaselineResult(
            baseline_name=self.name,
            kept_event_ids=kept,
            total_events=len(events),
            compression_ratio=len(kept) / len(events),
        )


# ---------------------------------------------------------------------------
# Baseline 3: Scene-Change Summarizer
# ---------------------------------------------------------------------------

class SceneChangeSummarizer:
    """
    Divide the video into fixed-length time windows and keep one representative
    event from each window (the highest-confidence event in that window).

    Simulates a naive scene-change-based approach where summarization is
    driven by temporal boundaries rather than semantic content.

    Expected weakness vs TCE:
      - Windows may split mid-narrative (entry in window 1, exit in window 2)
      - Empty windows produce no output even if adjacent windows have rich content
      - No distinction between types of events
    """

    name = "scene_change"

    def __init__(self, window_ms: float = 5000.0) -> None:
        """Args: window_ms — each temporal window in milliseconds."""
        self.window_ms = window_ms

    def summarize(
        self, events: list[Event], target_ratio: float = 0.40
    ) -> BaselineResult:
        if not events:
            return BaselineResult(self.name, set(), 0, 0.0)

        if not events:
            return BaselineResult(self.name, set(), 0, 0.0)

        kept: set[str] = set()
        # Group by window
        windows: dict[int, list[Event]] = {}
        for event in events:
            window_idx = int(event.start_ms // self.window_ms)
            windows.setdefault(window_idx, []).append(event)

        # Keep best event per window
        for window_events in windows.values():
            best = max(window_events, key=lambda e: e.confidence)
            kept.add(best.event_id)

        # Apply ratio cap — sort kept by confidence and trim if over ratio
        n_keep = max(1, int(len(events) * target_ratio))
        if len(kept) > n_keep:
            kept_events = [e for e in events if e.event_id in kept]
            kept_events.sort(key=lambda e: e.confidence, reverse=True)
            kept = {e.event_id for e in kept_events[:n_keep]}

        return BaselineResult(
            baseline_name=self.name,
            kept_event_ids=kept,
            total_events=len(events),
            compression_ratio=len(kept) / len(events),
        )
