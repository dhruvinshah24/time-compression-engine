# Phase 8 Report — Story Preservation + Event Graph

## Phase Name
Story Preservation + Event Graph (Phase 8)

## Objectives
- Transition from isolated events to narrative chains
- Classify each actor's event arc by completeness
- Score narrative importance of each story segment
- Build a relational event graph for graph-based compression policy
- Detect cross-track interactions (co-occurring events)
- Provide ranked segments to Phase 9 (Ranking Engine)

## Pre-Phase 8 Addition

### ConfidenceVector `components` sub-key
Per mentor recommendation: confidence is now exposed as:
```json
{
  "fused": 0.815,
  "components": {
    "detection": 0.85,
    "motion": 0.78,
    "rule": 0.83,
    "track_stability": 0.70,
    "scene_reliability": 1.0
  }
}
```
Flat keys retained for backward compatibility. This makes it immediately clear why the fused score is what it is.

## Algorithms Implemented

### 1. Story Preservation — Actor-Centric Narrative Grouping

**Algorithm:**
1. Group events by `track_id` → one event thread per actor
2. Classify completeness of each thread:
   - `COMPLETE`: entry event + ≥1 action + exit event (full arc, highest value)
   - `PARTIAL`: ≥2 events, missing entry or exit
   - `ENTRY_ONLY`: appeared but no further events (truncated/occluded)
   - `EXIT_ONLY`: exited without earlier events (already present at recording start)
   - `MINIMAL`: single event

3. Run `ContinuityChecker` per segment:
   - Temporal ordering validation
   - Invalid sequence detection (e.g. `person_walking` after `person_left_scene`)
   - Large time gap warnings (>10s within a segment)

4. Compute `narrative_score`:

```
narrative_score = (
    0.40 × mean_event_confidence
  + 0.30 × completeness_factor    # COMPLETE=1.0, PARTIAL=0.6, etc.
  + 0.20 × length_factor          # min(events/5, 1.0)
  + 0.10 × duration_factor        # min(duration_ms/5000, 1.0)
) × (1 - coherence_penalty)      # -10% per continuity issue, max -40%
```

5. Detect co-occurring segments (actors present at the same time)

### 2. Event Graph — Relational Event Structure

**Two edge types implemented:**

| Edge Type | Condition | Weight | Purpose |
|---|---|---|---|
| `SAME_TRACK_TEMPORAL` | Same track, consecutive events | 1.0 | Narrative thread |
| `CO_OCCURRENCE` | Different tracks, time windows overlap within 2s | 0.5 | Interaction signal |

**Graph analysis:**
- `hub_nodes(n)` — most connected events (highest degree)
- `isolated_nodes()` — events with no connections
- `subgraph_for_track(track_id)` — extract one actor's narrative sub-graph

**Research significance:** The graph answers "which events must be preserved together?" — this is what Phase 9 (Compression Policy) uses instead of just confidence scores.

## StoryCompleteness Taxonomy

```
Person entered → Person walking → Person picked parcel → Person exited
      ↑                ↑                    ↑                   ↑
   ENTRY_EVENT     ACTION_EVENT         ACTION_EVENT         EXIT_EVENT

= COMPLETE story segment (narrative_score ~0.85)
```

vs.

```
Person walking (no entry, no exit)
= PARTIAL segment (narrative_score ~0.50)
```

## Files Implemented

| File | Purpose |
|---|---|
| `engines/temporal/story_preservation/config.py` | StoryConfig with narrative score weights |
| `engines/temporal/story_preservation/continuity.py` | ContinuityChecker — temporal + semantic validation |
| `engines/temporal/story_preservation/story_builder.py` | StoryBuilder, StorySegment, StoryCompleteness |
| `engines/temporal/event_graph/config.py` | EventGraphConfig |
| `engines/temporal/event_graph/graph_builder.py` | EventGraph, EventNode, EventEdge, EdgeRelationship |
| `pipeline/stages/s09_story_build.py` | Pipeline stage |
| `tests/unit/test_story_preservation.py` | Unit + integration test suite |

## Test Results

```
40 tests — 40 passed, 0 failed
(273 total including all previous phases)
Run time: 2.75s total
```

### Integration tests (full 5-stage chain: Track → Motion → Event → Fusion → Story + Graph):

| Test | Expected | Result |
|---|---|---|
| Single person → story segment | ≥1 segment with score > 0 | ✅ |
| Two people → two segments, two tracks | len(track_ids) ≥ 2 | ✅ |
| Graph has SAME_TRACK edges | ≥1 SAME_TRACK_TEMPORAL edge | ✅ |
| Narrative scores non-zero | All scores > 0 | ✅ |
| Ranked segments descending | score[i] ≥ score[i+1] | ✅ |

## Data Contract (for Phase 9: Ranking Engine)

```python
# StorySegment passed to Phase 9
segment = StorySegment(
    segment_id="seg_7_a3f1c2",
    track_ids={7},
    events=[ev_entered, ev_walking, ev_loitering, ev_left],
    completeness=StoryCompleteness.COMPLETE,
    narrative_score=0.874,
    mean_confidence=0.821,
    start_ms=1200.0,
    end_ms=9800.0,
    is_coherent=True,
    interacting_segment_ids=["seg_3_b2d4e1"],  # concurrent actor
)

# EventGraph passed to Phase 9
graph.hub_nodes(5)  # most connected events to preserve
graph.subgraph_for_track(7)  # extract actor's arc
```

## Known Issues / Limitations
- `ContinuityChecker` validates structural coherence only. Deep causal reasoning (e.g. `door_opened → person_entered`) is planned for Phase 9 `hybrid_reasoner.py`.
- `SPATIAL_PROXIMITY` edges not yet implemented. Requires bbox history at the time of each event — Phase 9 enhancement.
- Multi-track story segments (e.g. two people interacting) are detected as separate segments that reference each other via `interacting_segment_ids`, not merged into a single segment. Merging is a Phase 10 enhancement.
- Narrative score weights (0.40/0.30/0.20/0.10) are initial priors. Empirical calibration on annotated benchmark corpus planned for Phase 10.

## Dependencies Added
- None. Pure Python + NumPy (already in requirements.txt).
