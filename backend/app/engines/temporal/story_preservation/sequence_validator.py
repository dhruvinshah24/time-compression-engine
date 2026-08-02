"""
Narrative Validator — validates the integrity of the compression result
before the final video is exported.

Per mentor guidance: insert a validation step between compression and export.

"The validator doesn't need to be complicated. It simply checks things like:
  - every kept COMPLETE chain is still complete
  - no chain starts with Exit
  - no chain ends with Entry
  - no orphaned events remain
  - graph connectivity is still valid"

Design: validation failures are classified as either ERROR or WARNING.
  ERROR   → the export stage should halt and log the violation.
  WARNING → the export can proceed but the issue is recorded for the report.

This is the final consistency gate before producing the highlight video.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.engines.semantic.event_understanding.engine import Event
from app.engines.semantic.event_understanding.rules import EventType
from app.engines.temporal.event_graph.graph_builder import EdgeRelationship, EventGraph
from app.engines.temporal.story_preservation.story_builder import (
    StoryCompleteness,
    StorySegment,
)


_ENTRY_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_ENTERED_SCENE,
    EventType.OBJECT_APPEARED,
})
_EXIT_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_LEFT_SCENE,
    EventType.OBJECT_DISAPPEARED,
})
_ACTION_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_WALKING, EventType.PERSON_RUNNING,
    EventType.PERSON_STANDING, EventType.PERSON_LOITERING,
    EventType.VEHICLE_APPROACHING, EventType.VEHICLE_RECEDING,
    EventType.VEHICLE_STATIONARY,
})


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ValidationIssue:
    severity: IssueSeverity
    check: str           # which check produced this
    description: str
    segment_id: str | None = None
    event_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity.value,
            "check": self.check,
            "description": self.description,
            "segment_id": self.segment_id,
            "event_ids": self.event_ids,
        }


@dataclass
class ValidationReport:
    """
    Summary of all validation checks run on the compression output.

    is_valid:  True only when there are zero ERROR-severity issues.
               Warnings are tolerated.
    """
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    # Convenience stats
    complete_chains_intact: int = 0
    chains_checked: int = 0
    orphaned_events: int = 0

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "error_count": len(self.errors()),
            "warning_count": len(self.warnings()),
            "complete_chains_intact": self.complete_chains_intact,
            "chains_checked": self.chains_checked,
            "orphaned_events": self.orphaned_events,
            "issues": [i.to_dict() for i in self.issues],
        }


class NarrativeValidator:
    """
    Final consistency gate before video export.

    Runs five checks on the set of kept events and segments:

      1. complete_chain_integrity — every COMPLETE segment still has entry+action+exit
      2. no_chain_starts_with_exit — entry point of each kept segment is valid
      3. no_chain_ends_with_entry  — exit point of each kept segment is valid
      4. no_orphaned_events       — every kept event belongs to a kept segment
      5. graph_connectivity       — kept events within each track remain connected
    """

    def validate(
        self,
        kept_segments: list[StorySegment],
        kept_event_ids: set[str],
        event_graph: EventGraph | None = None,
        all_events_by_id: dict[str, Event] | None = None,
    ) -> ValidationReport:
        """
        Run all validation checks.

        Args:
            kept_segments:    Segments that survived the compression policy.
            kept_event_ids:   Set of event IDs that survived (may include
                              events from partially kept segments if
                              chain_atomicity was off).
            event_graph:      EventGraph from Phase 8 (optional — used for
                              graph connectivity check).
            all_events_by_id: Full event registry for orphan detection.

        Returns:
            ValidationReport — is_valid=True iff no ERROR issues.
        """
        issues: list[ValidationIssue] = []

        complete_intact = 0
        chains_checked = 0

        for seg in kept_segments:
            chains_checked += 1
            # Only consider events that actually survived compression
            seg_events = [e for e in seg.events if e.event_id in kept_event_ids]

            if not seg_events:
                continue

            event_types = {e.event_type for e in seg_events}
            has_entry = bool(event_types & _ENTRY_EVENTS)
            has_exit = bool(event_types & _EXIT_EVENTS)
            has_action = bool(event_types & _ACTION_EVENTS)

            # ── Check 1: complete chain integrity ──────────────────────────
            if seg.completeness == StoryCompleteness.COMPLETE:
                if has_entry and has_exit and has_action:
                    complete_intact += 1
                else:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        check="complete_chain_integrity",
                        description=(
                            f"Segment {seg.segment_id} was COMPLETE but after "
                            f"compression is missing: "
                            + (", ".join(filter(None, [
                                "entry" if not has_entry else None,
                                "action" if not has_action else None,
                                "exit" if not has_exit else None,
                            ])))
                        ),
                        segment_id=seg.segment_id,
                    ))

            # ── Check 2: no chain starts with exit ─────────────────────────
            ordered = sorted(seg_events, key=lambda e: e.start_ms)
            if ordered[0].event_type in _EXIT_EVENTS:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    check="no_chain_starts_with_exit",
                    description=(
                        f"Segment {seg.segment_id} starts with exit event "
                        f"'{ordered[0].event_type}' — narrative may be confusing."
                    ),
                    segment_id=seg.segment_id,
                    event_ids=[ordered[0].event_id],
                ))

            # ── Check 3: no chain ends with entry ──────────────────────────
            if ordered[-1].event_type in _ENTRY_EVENTS:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    check="no_chain_ends_with_entry",
                    description=(
                        f"Segment {seg.segment_id} ends with entry event "
                        f"'{ordered[-1].event_type}' — story is unresolved."
                    ),
                    segment_id=seg.segment_id,
                    event_ids=[ordered[-1].event_id],
                ))

        # ── Check 4: no orphaned events ────────────────────────────────────
        orphaned = 0
        if all_events_by_id is not None:
            seg_event_ids: set[str] = {
                e.event_id for seg in kept_segments for e in seg.events
            }
            for eid in kept_event_ids:
                if eid not in seg_event_ids and eid in all_events_by_id:
                    orphaned += 1
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        check="no_orphaned_events",
                        description=(
                            f"Event {eid} is in kept_event_ids but not in "
                            f"any kept segment."
                        ),
                        event_ids=[eid],
                    ))

        # ── Check 5: graph connectivity ────────────────────────────────────
        if event_graph is not None:
            kept_nodes = {
                eid for eid in kept_event_ids
                if eid in event_graph.nodes
            }
            # For each kept event, check that its SAME_TRACK_TEMPORAL in-edges
            # either also point to a kept event or are the first in the chain.
            for eid in kept_nodes:
                node = event_graph.nodes[eid]
                same_track_in = [
                    edge_id for edge_id in node.in_edge_ids
                ]
                # Find edges where source is not kept
                for edge in event_graph.edges:
                    if (edge.target_node_id == eid
                            and edge.relationship == EdgeRelationship.SAME_TRACK_TEMPORAL
                            and edge.source_node_id not in kept_nodes):
                        issues.append(ValidationIssue(
                            severity=IssueSeverity.WARNING,
                            check="graph_connectivity",
                            description=(
                                f"Event {eid} has a SAME_TRACK_TEMPORAL predecessor "
                                f"{edge.source_node_id} that was discarded — "
                                f"chain is disconnected."
                            ),
                            event_ids=[eid, edge.source_node_id],
                        ))

        is_valid = all(i.severity != IssueSeverity.ERROR for i in issues)

        return ValidationReport(
            is_valid=is_valid,
            issues=issues,
            complete_chains_intact=complete_intact,
            chains_checked=chains_checked,
            orphaned_events=orphaned,
        )
