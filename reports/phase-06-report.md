# Phase 6 Report — Semantic Event Understanding

## Phase Name
Semantic Event Understanding (Phase 6)

## Objectives
- Answer "what happened?" rather than "what is visible?"
- Generate structured Event objects with full provenance from tracks + motion profiles
- Every event traceable to the exact rule that fired (explainability guarantee)
- Evidence dict on every event — cite-able in a viva or paper
- Support camera motion suppression
- Include integration tests: full chain Synthetic Track → Motion → Event

## Algorithm Implemented
**Rule-based Event Understanding via Declarative Knowledge Base**

See `research/algorithms.md` for rationale.

### Design decision: why rule-based?
Three reasons this matters for a research project:

1. **Interpretable**: Every event can be explained in one sentence —
   "Track 7 was classified as person_walking because its speed class was WALKING
   and it lasted 3+ frames."

2. **Extensible without retraining**: Adding a new event type (e.g., `crowd_forming`)
   requires one new `EventRule` entry in `rules.py`. No weights to retrain.

3. **Defensible in a viva**: Reviewers can inspect every rule. There is no black box.

Hybrid (rule + LLM) reasoning is planned for Phase 9 in `hybrid_reasoner.py`.
The interface does not change.

## Pre-Phase 6 addition: Motion Confidence

Implemented per mentor recommendation before Phase 6 began.

**Formula:**
```
motion_confidence = 0.4 × length_factor
                  + 0.4 × detection_confidence
                  + 0.2 × velocity_stability
```

Where:
- `length_factor` = min(matched_frames / 10, 1.0)
- `detection_confidence` = mean confidence from track observations
- `velocity_stability` = 1 / (1 + coefficient_of_variation_of_speed)

**Effect:** Short tracks, noisy detections, and erratic motion get lower confidence.
This confidence feeds into Phase 7 (Confidence Fusion) as a signal weight.

## Files Implemented

| File | Purpose |
|---|---|
| `engines/semantic/event_understanding/config.py` | EventUnderstandingConfig |
| `engines/semantic/event_understanding/rules.py` | EventRule + KNOWLEDGE_BASE (12 rules) |
| `engines/semantic/event_understanding/engine.py` | EventUnderstandingEngine + Event + EventUnderstandingResult |
| `pipeline/stages/s07_event_understand.py` | Pipeline stage |
| `tests/unit/test_event_understanding.py` | Unit + integration test suite |

## Knowledge Base (12 rules)

| Rule | Event Type | Key Conditions |
|---|---|---|
| rule_person_standing | person_standing | person + stationary |
| rule_person_walking | person_walking | person + slow/walking speed |
| rule_person_running | person_running | person + fast speed |
| rule_person_loitering | person_loitering | person + stationary + ≥5s duration |
| rule_person_entered | person_entered_scene | person + new track |
| rule_person_left | person_left_scene | person + ended track |
| rule_vehicle_approaching | vehicle_approaching | vehicle + approach signal |
| rule_vehicle_receding | vehicle_receding | vehicle + recede signal |
| rule_vehicle_stationary | vehicle_stationary | vehicle + stationary |
| rule_object_appeared | object_appeared | any + new track |
| rule_object_disappeared | object_disappeared | any + ended track |

## Test Results

```
35 tests — 35 passed, 0 failed
(204 total including all previous phases)
Run time: 2.23s total
```

### Integration tests (per mentor guidance):

| Test | Chain | Expected | Result |
|---|---|---|---|
| person_walking | Bboxes moving right → MotionAnalyzer → EventEngine | person_walking | ✅ |
| person_standing | Stationary bboxes → MotionAnalyzer → EventEngine | person_standing | ✅ |
| vehicle_approaching | Growing bboxes → MotionAnalyzer → EventEngine | vehicle_approaching | ✅ |
| person_loitering | 20 frames stationary (8s) → EventEngine | person_loitering | ✅ |
| evidence populated | Any event → evidence dict has 'rule' key | Always present | ✅ |
| empty scene | No tracks → EventEngine | Zero events | ✅ |
| motion_confidence | Long consistent track → MotionAnalyzer | confidence > 0.5 | ✅ |

## Event Data Contract (for Phase 8)

```python
Event(
    event_id="uuid",           # globally unique
    event_type="person_walking",
    track_id=7,
    class_name="person",
    rule_name="rule_person_walking",   # audit trail
    confidence=0.82,
    evidence={
        "rule": "rule_person_walking",
        "class_match": "person",
        "speed_class": "walking",
        "track_id": 7,
        "track_length_ms": 1200.0,
    },
    start_frame=5,
    end_frame=15,
    start_ms=1000.0,
    end_ms=3000.0,
)
```

## Phase 7 Integration Contract
`motion_confidence` from MotionProfile is now available on every track's profile.
Phase 7 (Confidence Fusion) uses it as one of its input signals:
```python
C_fused = w_detection × detection_confidence
        + w_motion    × motion_confidence
        + w_event     × event_confidence
```

## Known Issues / Limitations
- Loitering threshold (5000ms) is hard-coded in the rule. Should move to config in Phase 10.
- Camera motion suppression only works when ≥3 simultaneous tracks are present
  (limitation from Phase 5 camera motion detector).
- No spatial overlap between events checked yet — two overlapping events at same time
  are both kept. Deduplication planned for Phase 8 (Event Graph merge step).

## Dependencies Added
- None. Pure Python.
