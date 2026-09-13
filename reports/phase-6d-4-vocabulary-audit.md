# Phase 6D.4 — Vocabulary Audit Report

**Phase:** 6D.4  
**Baseline commit:** `bd9d18e`  
**Previous experiment:** `cb128dc` (Phase 6D.3)  
**Date:** 2026-09-13  

---

## 1. Objective

Determine the exact event_type strings emitted by S07 for each label observed in the Phase 6D.3 300s run that is absent from `StoryBuilder._ACTION_EVENTS`. Trace whether each label represents an observable action suitable for story completion.

---

## 2. Traced Label Sources

### 2.1 Architecture — How narrative_builder emits labels

S07 Pass 7 (`narrative_builder`, [`s07_event_understand.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/pipeline/stages/s07_event_understand.py) lines 701–760):

```python
# Line 735 — event_type is set directly to activity.label
narrative_events.append(Event(
    event_type=activity.label,   # ← ActivityClassifier.classify() label string
    ...
    rule_name="narrative_builder",
))
```

This means the `event_type` in the event stream equals exactly the label returned by `ActivityClassifier.classify()` — not an `EventType.*` constant.

### 2.2 Architecture — How activity_state_machine emits labels

S07 Pass 5 (`activity_state_machine`, lines 476–543): Uses `EventType.*` constants, e.g. `EventType.PERSON_WALKING = "person_walking"`. These ARE already in `_ACTION_EVENTS`.

### 2.3 Architecture — How temporal_pose_bbox emits labels

S07 Pass 3b (`temporal_pose_bbox`, lines 440–468): Uses `TemporalPoseAnalyzer.to_pipeline_event_dict()` which maps:
- `STATE_CROUCHING → "person_crouching_sustained"` (pose_temporal.py line 478)

These labels are NOT `EventType.*` constants and NOT in `_ACTION_EVENTS`.

---

## 3. Label Audit Table

| Emitted label | Producer module | Rule name | Evidence fields | Observable action? | Current StoryBuilder recognition | Decision |
|---|---|---|---|---|---|---|
| `"running"` | `ActivityClassifier.classify()` | `narrative_builder` | mean_speed, duration_s, reason="high_velocity" | **YES** — person in rapid motion, observable and meaningful | `_ACTION_EVENTS` contains `"person_running"` (from EventType.PERSON_RUNNING), NOT `"running"` | **ADD** |
| `"walking_upstairs"` | `ActivityClassifier._detect_stairs()` | `narrative_builder` | stair_conf, stair_direction, mean_speed | **YES** — physically distinct from walking on flat surface; directional | Not present in `_ACTION_EVENTS` at any alias | **ADD** |
| `"walking_downstairs"` | `ActivityClassifier._detect_stairs()` | `narrative_builder` | stair_conf, stair_direction, mean_speed | **YES** — same rationale as upstairs | Not present in `_ACTION_EVENTS` at any alias | **ADD** |
| `"person_crouching_sustained"` | `TemporalPoseAnalyzer` | `temporal_pose_bbox` | state_duration_frames, source="TemporalPoseAnalyzer", note="thresholds not yet calibrated" | **CONDITIONAL** — posture change is observable, but evidence note says thresholds uncalibrated | Not present in `_ACTION_EVENTS` | **DEFER** |

---

## 4. Decision Rationale

### 4.1 `"running"` → ADD

**Evidence trail:**
- ActivityClassifier (line 233): `label="running"`, triggered when `mean_speed >= RUN_THRESHOLD`
- narrative_builder (line 735): `event_type=activity.label` → `event_type="running"`
- `EventType.PERSON_RUNNING = "person_running"` — different string
- `_ACTION_EVENTS` contains `EventType.PERSON_RUNNING = "person_running"` — MISMATCH
- In Phase 6D.3 300s run: 14 events of type `"running"` produced

Running is a physically observable, unambiguous action. The narrative_builder pattern emitting `"running"` directly from `activity.label` is the intended design. Adding `"running"` to `_ACTION_EVENTS` aligns producer vocabulary with story vocabulary. This is identical in structure to the Phase 6D `"cycling"` fix.

**Is it safe?** Yes. `"running"` is not an entry or exit event. It is a mid-track activity event. Adding it to `_ACTION_EVENTS` means tracks with entry + running + exit become COMPLETE stories — which is the correct behavior.

### 4.2 `"walking_upstairs"` → ADD

**Evidence trail:**
- ActivityClassifier `_detect_stairs()` (line 220): `label=f"walking_{stair_dir}stairs"` → `"walking_upstairs"`
- narrative_builder (line 724): `"walking_upstairs": f"{label} is walking up stairs"` — explicitly described
- Not an `EventType.*` constant; not in `_ACTION_EVENTS`

Stair walking is directional and observable. The narrative_builder has a purpose-written description for it. It is a meaningful action event for a story arc (person entered → walked upstairs → exited). Adding it does not create a safety or semantic risk.

### 4.3 `"walking_downstairs"` → ADD

Same rationale as `"walking_upstairs"`. Symmetric label from the same classifier path.

### 4.4 `"person_crouching_sustained"` → DEFER

**Evidence trail:**
- TemporalPoseAnalyzer (pose_temporal.py line 478): `STATE_CROUCHING → "person_crouching_sustained"`
- rule_name: `"temporal_pose_bbox"` (different producer from narrative_builder)
- Evidence note (S07 line 452): `"IMPLEMENTED — thresholds not yet calibrated against real labelled footage. Treat events as candidate observations."`

**Reason for deferral:** The event's own evidence field explicitly states the thresholds are not calibrated. In Phase 6B, 4 `person_crouching_sustained` events were observed in archive_001 (a 1948 pedestrian safety film with no intended crouching). Including an uncalibrated event in `_ACTION_EVENTS` would silently promote unvalidated classifications to COMPLETE stories. This is a different risk profile from `"running"` and `"walking_upstairs"`, which have straightforward velocity-based triggers.

The Phase 6D.4 experiment adds ONLY: `"running"`, `"walking_upstairs"`, `"walking_downstairs"`.

---

## 5. Labels NOT added and why

| Label | Reason not added |
|---|---|
| `"person_crouching_sustained"` | Thresholds explicitly noted as uncalibrated in source evidence |
| `"loitering"` | Not observed in Phase 6D.3 run. Present in narrative_builder but `_ACTION_EVENTS` already has `EventType.PERSON_LOITERING = "person_loitering"` — check if this is another mismatch if loitering appears in future runs |
| `"walking"` | ActivityClassifier emits `"walking"` but `_ACTION_EVENTS` has `"person_walking"` — however, the activity_state_machine (Pass 5) emits `"person_walking"` via `EventType.PERSON_WALKING`. If Pass 5 runs, narrative_builder's `"walking"` is a duplicate and may be suppressed. Do not add both until further evidence. |
| `"entering_scene"` | ActivityClassifier emits this for ≤2 obs tracks — not an action event, semantically equivalent to entry |
| `"standing"` | ActivityClassifier emits `"standing"` but state machine emits `"person_standing"`. `_ACTION_EVENTS` has `"person_standing"`. Same pattern as walking. |

---

## 6. Verification Prediction

Adding `"running"`, `"walking_upstairs"`, `"walking_downstairs"`:

Phase 6D.3 had 14 running + 7 walking_upstairs + 3 walking_downstairs = **24 narrative action events** that were unrecognized by StoryBuilder. If any of these co-occur with entry+exit events for the same track, those tracks will now produce COMPLETE stories.

Predicted complete story count increase: > 1 (Phase 6D.3 result), likely 5–15 based on Phase 6D.3 event distribution.

---

## 7. Explicit Notes on Not Fixing

- **`"person_crouching_sustained"`:** Deferred. Not added.
- **`"loitering"` mismatch:** Deferred (not observed in Phase 6D.3).
- **`"walking"` mismatch:** Deferred (Pass 5 may overlap; not tested).
- No producers were renamed.
- No upstream labels were changed.
- ActivityClassifier thresholds: unchanged.
