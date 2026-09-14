"""
Event graph route — GET /event-graph/{video_id}

Builds a real relationship graph from detected events.
No ML inference. Pure read-only aggregation from the event repository.

Graph structure:
  nodes: one node per identified person/track (or per unique event type for scene-level events)
  edges: temporal co-occurrence within a 10-second sliding window

Edge types:
  TEMPORAL_SEQUENCE  — same actor's events in sequence
  CO_OCCURRENCE      — two different actors active within 10s of each other
"""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_event_repo, get_video_repo

router = APIRouter()
logger = logging.getLogger(__name__)

_CO_OCCURRENCE_WINDOW_MS = 10_000  # 10 seconds


@router.get("/")
async def list_event_graphs():
    """List all available event graphs."""
    return []


@router.get("/{video_id}")
async def get_event_graph(video_id: str):
    """
    Build and return an event relationship graph for a video.

    Returns:
      nodes: list of actor nodes (persons, tracks, or scene-level)
      edges: list of temporal relationships between nodes
      stats: summary statistics
    """
    video_repo = get_video_repo()
    video = await video_repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    event_repo = get_event_repo()
    events = await event_repo.list_by_video(video_id)

    if not events:
        return {
            "video_id": video_id,
            "nodes": [],
            "edges": [],
            "stats": {"node_count": 0, "edge_count": 0, "event_count": 0},
        }

    # ── Build actor map ────────────────────────────────────────────────────────
    # actor_key → { events[], first_seen_ms, last_seen_ms, event_types set }
    actor_map: dict[str, dict] = {}

    for evt in events:
        evidence = evt.get("evidence") or {}
        person_label = evidence.get("person_label") or evt.get("person_label")
        track_id = evt.get("track_id")
        event_type = evt.get("event_type") or evt.get("type") or "unknown"

        if person_label:
            key = f"person:{person_label}"
            label = person_label
            node_type = "person"
        elif track_id is not None:
            key = f"track:{track_id}"
            label = f"Track {track_id}"
            node_type = "track"
        else:
            key = f"event:{event_type}"
            label = event_type.replace("_", " ").title()
            node_type = "scene"

        ts = evt.get("start_ms") or evt.get("timestamp_ms") or 0

        if key not in actor_map:
            actor_map[key] = {
                "key": key,
                "label": label,
                "node_type": node_type,
                "events": [],
                "first_seen_ms": ts,
                "last_seen_ms": ts,
                "event_types": set(),
            }

        actor_map[key]["events"].append(evt)
        actor_map[key]["last_seen_ms"] = max(actor_map[key]["last_seen_ms"], ts)
        actor_map[key]["first_seen_ms"] = min(actor_map[key]["first_seen_ms"], ts)
        actor_map[key]["event_types"].add(event_type)

    # ── Build nodes ────────────────────────────────────────────────────────────
    nodes = []
    for i, (key, actor) in enumerate(actor_map.items()):
        duration_s = (actor["last_seen_ms"] - actor["first_seen_ms"]) / 1000.0
        nodes.append({
            "id": key,
            "label": actor["label"],
            "node_type": actor["node_type"],
            "event_count": len(actor["events"]),
            "first_seen_ms": actor["first_seen_ms"],
            "last_seen_ms": actor["last_seen_ms"],
            "duration_s": round(duration_s, 1),
            "event_types": sorted(actor["event_types"]),
            "index": i,
        })

    # ── Build edges ────────────────────────────────────────────────────────────
    edges = []
    edge_keys: set[str] = set()
    node_keys = list(actor_map.keys())

    # TEMPORAL_SEQUENCE — connect sequential events of same actor
    for key, actor in actor_map.items():
        if len(actor["events"]) >= 2:
            evts = sorted(actor["events"], key=lambda e: e.get("start_ms") or 0)
            for j in range(len(evts) - 1):
                et1 = evts[j].get("event_type") or "event"
                et2 = evts[j+1].get("event_type") or "event"
                gap_ms = (evts[j+1].get("start_ms") or 0) - (evts[j].get("start_ms") or 0)
                if gap_ms <= 60_000:  # only connect if within 60s gap
                    edge_key = f"{key}:SEQ:{j}"
                    if edge_key not in edge_keys:
                        edge_keys.add(edge_key)
                        edges.append({
                            "id": edge_key,
                            "source": key,
                            "target": key,
                            "relation": "TEMPORAL_SEQUENCE",
                            "label": f"{et1.replace('_',' ')} → {et2.replace('_',' ')}",
                            "weight": 1,
                            "gap_ms": gap_ms,
                        })

    # CO_OCCURRENCE — different actors active within window
    for i, key_a in enumerate(node_keys):
        for key_b in node_keys[i+1:]:
            if key_a == key_b:
                continue
            actor_a = actor_map[key_a]
            actor_b = actor_map[key_b]

            # Check temporal overlap
            overlap_count = 0
            for evt_a in actor_a["events"]:
                ts_a = evt_a.get("start_ms") or 0
                for evt_b in actor_b["events"]:
                    ts_b = evt_b.get("start_ms") or 0
                    if abs(ts_a - ts_b) <= _CO_OCCURRENCE_WINDOW_MS:
                        overlap_count += 1

            if overlap_count > 0:
                edge_key = f"CO:{key_a}:{key_b}"
                if edge_key not in edge_keys:
                    edge_keys.add(edge_key)
                    edges.append({
                        "id": edge_key,
                        "source": key_a,
                        "target": key_b,
                        "relation": "CO_OCCURRENCE",
                        "label": f"Co-active {overlap_count}×",
                        "weight": overlap_count,
                        "gap_ms": None,
                    })

    # Only keep cross-actor CO_OCCURRENCE edges (filter self-loops for sequence)
    cross_edges = [e for e in edges if e["relation"] == "CO_OCCURRENCE"]
    seq_edges_per_node = {}
    for e in edges:
        if e["relation"] == "TEMPORAL_SEQUENCE":
            seq_edges_per_node.setdefault(e["source"], []).append(e)

    # Return one sequence summary per actor (first → last event type)
    summary_seq_edges = []
    for key, actor in actor_map.items():
        if len(actor["events"]) >= 2:
            evts = sorted(actor["events"], key=lambda e: e.get("start_ms") or 0)
            et_first = evts[0].get("event_type") or "event"
            et_last = evts[-1].get("event_type") or "event"
            edge_key = f"{key}:ARC"
            summary_seq_edges.append({
                "id": edge_key,
                "source": key,
                "target": key,
                "relation": "ACTOR_ARC",
                "label": f"{et_first.replace('_',' ')} → {et_last.replace('_',' ')}",
                "weight": len(evts),
                "gap_ms": None,
            })

    final_edges = summary_seq_edges + cross_edges

    return {
        "video_id": video_id,
        "nodes": nodes,
        "edges": final_edges,
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(final_edges),
            "event_count": len(events),
            "co_occurrence_edges": len(cross_edges),
            "arc_edges": len(summary_seq_edges),
        },
    }
