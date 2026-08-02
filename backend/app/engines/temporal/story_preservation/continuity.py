"""
Continuity checker — validates temporal coherence of events within a story segment.

A story segment is temporally coherent if:
  1. Events are ordered in time (no backward jumps)
  2. The event sequence makes semantic sense (e.g. can't walk after leaving scene)
  3. The same actor is not simultaneously in two incompatible states

This module is intentionally simple for Phase 8.
It checks structural continuity, not deep semantic causality.
Causal reasoning is planned as a Phase 9 hybrid_reasoner enhancement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engines.semantic.event_understanding.engine import Event


@dataclass
class ContinuityReport:
    """Report of continuity checks for a single story segment."""
    segment_id: str
    is_coherent: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Event types that represent terminal states (nothing valid can follow)
_TERMINAL_EVENTS: frozenset[str] = frozenset({
    "person_left_scene",
    "object_disappeared",
})

# Impossible sequences: (event_A, event_B) pairs that shouldn't occur in order
_INVALID_SEQUENCES: list[tuple[str, str]] = [
    ("person_left_scene", "person_walking"),
    ("person_left_scene", "person_running"),
    ("person_left_scene", "person_standing"),
    ("person_left_scene", "person_loitering"),
    ("object_disappeared", "object_appeared"),   # same track only
]


class ContinuityChecker:
    """
    Validates temporal + semantic coherence of a sequence of events.

    Called by StoryBuilder on each candidate story segment.
    Issues don't discard a segment — they reduce its narrative score.
    """

    def check(self, segment_id: str, events: list[Event]) -> ContinuityReport:
        """
        Run continuity checks on an ordered event list.

        Args:
            segment_id: Identifier for logging.
            events:     Events ordered by start_ms (ascending).

        Returns:
            ContinuityReport with is_coherent flag and any issues found.
        """
        issues: list[str] = []
        warnings: list[str] = []

        if len(events) < 2:
            return ContinuityReport(segment_id, is_coherent=True)

        seen_terminal = False
        prev_event = events[0]

        for i, event in enumerate(events[1:], start=1):
            # ── Check 1: Temporal ordering ─────────────────────────────────
            if event.start_ms < prev_event.start_ms:
                issues.append(
                    f"Event {i} ({event.event_type}) starts before event {i-1} "
                    f"({prev_event.event_type}): {event.start_ms:.0f}ms < {prev_event.start_ms:.0f}ms"
                )

            # ── Check 2: Nothing follows a terminal event ──────────────────
            if seen_terminal:
                issues.append(
                    f"Event {i} ({event.event_type}) follows terminal event "
                    f"({prev_event.event_type}) — track {event.track_id}"
                )

            if prev_event.event_type in _TERMINAL_EVENTS:
                seen_terminal = True

            # ── Check 3: Invalid sequences ─────────────────────────────────
            for (a, b) in _INVALID_SEQUENCES:
                if prev_event.event_type == a and event.event_type == b:
                    issues.append(
                        f"Invalid sequence: {a} → {b} on track {event.track_id}"
                    )

            # ── Check 4: Large time gap (warning, not error) ───────────────
            gap_ms = event.start_ms - prev_event.end_ms
            if gap_ms > 10_000:  # 10-second gap in a single segment
                warnings.append(
                    f"Large time gap between events {i-1} and {i}: {gap_ms:.0f}ms"
                )

            prev_event = event

        return ContinuityReport(
            segment_id=segment_id,
            is_coherent=len(issues) == 0,
            issues=issues,
            warnings=warnings,
        )
