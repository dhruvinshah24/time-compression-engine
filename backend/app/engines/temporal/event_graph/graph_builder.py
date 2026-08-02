"""
Event Graph — Temporal Engine, Phase 8.

Represents events as nodes and their relationships as directed edges.

Research significance:
  This is what separates the Time Compression Engine from simple highlight
  detection. Instead of asking "which events are most confident?", the graph
  lets us ask "which events are most connected?" and "which sub-graphs
  form coherent narratives?"

  This aligns with the mentor's framing:
  "Think in terms of relationships, not isolated events."

Node: One Event
Edge types:
  SAME_TRACK_TEMPORAL  — consecutive events from the same track (strongest link)
  CO_OCCURRENCE        — events from different tracks overlapping in time

Future edge types (Phase 9):
  SPATIAL_PROXIMITY    — events near each other in frame space
  CAUSAL               — door_opened → person_entered (requires knowledge base)

Graph structure is a simple adjacency list + edge list.
No external graph library required — the graph is small (< 100 nodes per video segment).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from app.engines.semantic.event_understanding.engine import Event
from app.engines.temporal.event_graph.config import EventGraphConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Edge relationship enum
# ---------------------------------------------------------------------------

class EdgeRelationship(str, Enum):
    SAME_TRACK_TEMPORAL = "same_track_temporal"
    CO_OCCURRENCE = "co_occurrence"


# ---------------------------------------------------------------------------
# Graph data classes
# ---------------------------------------------------------------------------

@dataclass
class EventNode:
    """One event as a graph node."""
    node_id: str          # = event.event_id
    event: Event
    in_edge_ids: list[str] = field(default_factory=list)
    out_edge_ids: list[str] = field(default_factory=list)

    @property
    def degree(self) -> int:
        return len(self.in_edge_ids) + len(self.out_edge_ids)


@dataclass
class EventEdge:
    """A directed relationship between two events."""
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship: EdgeRelationship
    weight: float

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "source": self.source_node_id,
            "target": self.target_node_id,
            "relationship": self.relationship.value,
            "weight": round(self.weight, 4),
        }


@dataclass
class EventGraph:
    """
    The full event graph for a video.

    nodes: dict[event_id → EventNode]
    edges: list of all EventEdge objects

    Key graph statistics:
      - total_nodes: one per event
      - total_edges: sum of SAME_TRACK + CO_OCCURRENCE edges
      - hub_nodes: nodes with highest degree (most connected events)
      - isolated_nodes: events with no connections
    """
    nodes: dict[str, EventNode] = field(default_factory=dict)
    edges: list[EventEdge] = field(default_factory=list)

    def add_edge(
        self,
        source_event_id: str,
        target_event_id: str,
        relationship: EdgeRelationship,
        weight: float,
    ) -> EventEdge:
        edge = EventEdge(
            edge_id=str(uuid.uuid4()),
            source_node_id=source_event_id,
            target_node_id=target_event_id,
            relationship=relationship,
            weight=weight,
        )
        self.edges.append(edge)
        if source_event_id in self.nodes:
            self.nodes[source_event_id].out_edge_ids.append(edge.edge_id)
        if target_event_id in self.nodes:
            self.nodes[target_event_id].in_edge_ids.append(edge.edge_id)
        return edge

    def hub_nodes(self, top_n: int = 5) -> list[EventNode]:
        """Return the top_n most connected nodes."""
        return sorted(self.nodes.values(), key=lambda n: n.degree, reverse=True)[:top_n]

    def isolated_nodes(self) -> list[EventNode]:
        """Return nodes with no edges — events that don't connect to anything."""
        return [n for n in self.nodes.values() if n.degree == 0]

    def edges_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.edges:
            counts[e.relationship.value] = counts.get(e.relationship.value, 0) + 1
        return counts

    def subgraph_for_track(self, track_id: int) -> list[EventNode]:
        """All nodes from a specific track (for narrative extraction)."""
        return [
            n for n in self.nodes.values()
            if n.event.track_id == track_id
        ]

    def to_metrics_dict(self) -> dict:
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "edges_by_type": self.edges_by_type(),
            "isolated_nodes": len(self.isolated_nodes()),
            "hub_node_ids": [n.node_id for n in self.hub_nodes(3)],
        }


# ---------------------------------------------------------------------------
# EventGraphBuilder
# ---------------------------------------------------------------------------

class EventGraphBuilder:
    """
    Constructs the EventGraph from a list of fused events.

    Phase 8 implements two edge types:
      SAME_TRACK_TEMPORAL — consecutive events from the same actor (strong narrative link)
      CO_OCCURRENCE       — events from different actors at the same time (interaction signal)

    The graph is used by Phase 9 (Compression Policy) to answer:
      "Which events must be preserved together to maintain narrative coherence?"
    """

    def __init__(self, config: EventGraphConfig | None = None) -> None:
        self.config = config or EventGraphConfig()

    def build(self, events: list[Event]) -> EventGraph:
        """
        Build the event graph from a list of events.

        Args:
            events: Fused events in any order.

        Returns:
            EventGraph with SAME_TRACK_TEMPORAL and CO_OCCURRENCE edges.
        """
        graph = EventGraph()

        # ── Step 1: Add all events as nodes ───────────────────────────────
        for event in events:
            graph.nodes[event.event_id] = EventNode(
                node_id=event.event_id,
                event=event,
            )

        # ── Step 2: SAME_TRACK_TEMPORAL edges ─────────────────────────────
        # Group by track, sort by time, link consecutive events
        track_events: dict[int, list[Event]] = {}
        for event in events:
            track_events.setdefault(event.track_id, []).append(event)

        for track_id, tevents in track_events.items():
            tevents.sort(key=lambda e: e.start_ms)
            for i in range(len(tevents) - 1):
                graph.add_edge(
                    source_event_id=tevents[i].event_id,
                    target_event_id=tevents[i + 1].event_id,
                    relationship=EdgeRelationship.SAME_TRACK_TEMPORAL,
                    weight=self.config.same_track_edge_weight,
                )

        # ── Step 3: CO_OCCURRENCE edges ────────────────────────────────────
        # Cross-track pairs whose time windows overlap (or are within window)
        gap = self.config.max_co_occurrence_gap_ms
        event_list = sorted(events, key=lambda e: e.start_ms)

        for i, ev_a in enumerate(event_list):
            for ev_b in event_list[i + 1:]:
                # Stop early once ev_b starts too late
                if ev_b.start_ms > ev_a.end_ms + gap:
                    break
                # Skip same-track pairs (already covered by SAME_TRACK_TEMPORAL)
                if ev_a.track_id == ev_b.track_id:
                    continue
                # Check overlap
                if ev_a.start_ms <= ev_b.end_ms and ev_b.start_ms <= ev_a.end_ms + gap:
                    graph.add_edge(
                        source_event_id=ev_a.event_id,
                        target_event_id=ev_b.event_id,
                        relationship=EdgeRelationship.CO_OCCURRENCE,
                        weight=self.config.co_occurrence_weight,
                    )

        logger.info(
            "EventGraph: %d nodes, %d edges (%s)",
            len(graph.nodes), len(graph.edges), graph.edges_by_type(),
        )
        return graph
