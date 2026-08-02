"""
Evaluation metrics for comparing summarization approaches.

Produces the comparison table the mentor recommended:

  Baseline               | Compression Ratio | Completeness Retained | Broken Narratives | Chain Length
  -----------------------|-------------------|----------------------|-------------------|-------------
  Uniform sampling       | 0.40              | 0.33                 | 8                 | 1.2
  Motion-only            | 0.40              | 0.41                 | 5                 | 1.4
  Scene-change           | 0.40              | 0.38                 | 6                 | 1.3
  Time Compression Engine| 0.40              | 0.95                 | 0                 | 3.8

Each metric is computable from a set of kept_event_ids and the full
story segment list — so all approaches are compared on the same ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.engines.semantic.event_understanding.engine import Event
from app.engines.temporal.story_preservation.story_builder import (
    StoryCompleteness,
    StorySegment,
)


_ENTRY_EVENTS = frozenset({"person_entered_scene", "object_appeared"})
_EXIT_EVENTS = frozenset({"person_left_scene", "object_disappeared"})
_ACTION_EVENTS = frozenset({
    "person_walking", "person_running", "person_standing",
    "person_loitering", "vehicle_approaching", "vehicle_receding", "vehicle_stationary",
})


@dataclass
class SummaryMetrics:
    """
    Evaluation metrics for one summarization result.

    Computed from a set of kept_event_ids against the full story segment list.
    """
    approach_name: str
    compression_ratio: float

    # Narrative quality metrics
    story_completeness_retained: float   # fraction of COMPLETE arcs fully kept
    broken_narratives: int               # arcs with partial event coverage
    avg_chain_length: float              # mean events per kept arc

    # Event coverage
    total_events: int
    kept_events: int

    def to_dict(self) -> dict:
        return {
            "approach": self.approach_name,
            "compression_ratio": round(self.compression_ratio, 4),
            "story_completeness_retained": round(self.story_completeness_retained, 4),
            "broken_narratives": self.broken_narratives,
            "avg_chain_length": round(self.avg_chain_length, 4),
            "kept_events": self.kept_events,
            "total_events": self.total_events,
        }


@dataclass
class ComparisonTable:
    """Side-by-side comparison of multiple approaches."""
    rows: list[SummaryMetrics]

    def to_markdown(self) -> str:
        """Render the comparison table as GitHub-flavoured markdown."""
        header = (
            "| Approach | Ratio | Completeness | Broken | Chain Len |\n"
            "|---|---|---|---|---|\n"
        )
        rows = ""
        for m in self.rows:
            rows += (
                f"| {m.approach_name} "
                f"| {m.compression_ratio:.0%} "
                f"| {m.story_completeness_retained:.0%} "
                f"| {m.broken_narratives} "
                f"| {m.avg_chain_length:.1f} |\n"
            )
        return header + rows

    def best_by(self, metric: str) -> SummaryMetrics:
        """Return the row with the best value for the given metric."""
        if metric in ("story_completeness_retained", "avg_chain_length"):
            return max(self.rows, key=lambda m: getattr(m, metric))
        elif metric in ("broken_narratives",):
            return min(self.rows, key=lambda m: getattr(m, metric))
        raise ValueError(f"Unknown metric: {metric}")


def compute_metrics(
    approach_name: str,
    kept_event_ids: set[str],
    all_events: list[Event],
    segments: list[StorySegment],
) -> SummaryMetrics:
    """
    Compute evaluation metrics for a given set of kept events.

    Args:
        approach_name:    Label for the approach being evaluated.
        kept_event_ids:   The events this approach retained.
        all_events:       All events (ground truth).
        segments:         Story segments from Phase 8.

    Returns:
        SummaryMetrics for this approach.
    """
    total = len(all_events)
    kept = len(kept_event_ids)
    ratio = kept / total if total > 0 else 0.0

    # -- Narrative metrics --------------------------------------------------
    complete_segs = [s for s in segments if s.completeness == StoryCompleteness.COMPLETE]
    complete_fully_kept = 0
    broken = 0
    chain_lengths: list[int] = []

    for seg in segments:
        seg_event_ids = {e.event_id for e in seg.events}
        overlap = seg_event_ids & kept_event_ids
        if not overlap:
            continue  # segment entirely discarded — not broken, just gone

        # How many events of this segment are kept?
        n_kept = len(overlap)
        chain_lengths.append(n_kept)

        # Broken: some but not all events kept (chain atomicity violated)
        if 0 < n_kept < len(seg_event_ids):
            broken += 1

        # Complete arc integrity
        if seg.completeness == StoryCompleteness.COMPLETE and n_kept == len(seg_event_ids):
            complete_fully_kept += 1

    completeness_retained = (
        complete_fully_kept / len(complete_segs)
        if complete_segs else 1.0
    )
    avg_chain = float(np.mean(chain_lengths)) if chain_lengths else 0.0

    return SummaryMetrics(
        approach_name=approach_name,
        compression_ratio=ratio,
        story_completeness_retained=completeness_retained,
        broken_narratives=broken,
        avg_chain_length=avg_chain,
        total_events=total,
        kept_events=kept,
    )


def compare_all(
    tce_kept: set[str],
    all_events: list[Event],
    segments: list[StorySegment],
    target_ratio: float = 0.40,
) -> ComparisonTable:
    """
    Run all three baselines and the TCE, return a ComparisonTable.

    Args:
        tce_kept:      event_ids kept by the Time Compression Engine.
        all_events:    All events in the pipeline output.
        segments:      Story segments from Phase 8 (ground truth narratives).
        target_ratio:  Target compression ratio for all methods.
    """
    from app.evaluation.baselines.summarizers import (
        MotionOnlySummarizer,
        SceneChangeSummarizer,
        UniformSampler,
    )

    baselines = [
        ("Uniform Sampling", UniformSampler().summarize(all_events, target_ratio)),
        ("Motion Only", MotionOnlySummarizer().summarize(all_events, target_ratio)),
        ("Scene Change", SceneChangeSummarizer().summarize(all_events, target_ratio)),
    ]

    rows: list[SummaryMetrics] = []
    for name, baseline in baselines:
        rows.append(compute_metrics(name, baseline.kept_event_ids, all_events, segments))

    # TCE result
    rows.append(compute_metrics(
        "Time Compression Engine", tce_kept, all_events, segments
    ))

    return ComparisonTable(rows=rows)
