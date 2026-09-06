# Story Failure Audit — archive_001, 300 seconds, Phase 6C

**Phase:** 6C  
**Run:** archive_001, 300s, commit `3ba0660`  
**Date:** 2026-09-06  
**Subject:** Why does S09 produce 0 complete story segments despite 154 confirmed person tracks?

---

## Executive Summary

**Root cause of FAIL-008: `cycling` is not in StoryBuilder `_ACTION_EVENTS`.**

The StoryBuilder requires `entry + action + exit` for a COMPLETE segment. In the 300s run:
- The activity state machine produces `person_entered_scene` (ENTRY) and `person_left_scene` (EXIT) for confirmed tracks.
- The narrative builder produces `cycling` for 83.8% of those tracks.
- **`cycling` is not classified as an ACTION.** Tracks with entry+cycling+exit are classified PARTIAL.
- 10 tracks globally would be COMPLETE if `cycling` were added to `_ACTION_EVENTS`.

A second cause compounds the first: `running`, `walking_upstairs`, `walking_downstairs`, `person_sitting`, `person_crouching_sustained`, `person_fallen`, `person_reaching_up`, `group_gathering`, `light_turned_on`, `light_turned_off` are all also **unroled** — they contribute to no story category.

---

## Part D: Root Cause Tracing

### StoryBuilder Completeness Logic

Source: [`story_builder.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/engines/temporal/story_preservation/story_builder.py) — lines 50–61.

```python
_ENTRY_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_ENTERED_SCENE, EventType.OBJECT_APPEARED,
})
_EXIT_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_LEFT_SCENE, EventType.OBJECT_DISAPPEARED,
})
_ACTION_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_WALKING, EventType.PERSON_RUNNING,
    EventType.PERSON_STANDING, EventType.PERSON_LOITERING,
    EventType.VEHICLE_APPROACHING, EventType.VEHICLE_RECEDING,
    EventType.VEHICLE_STATIONARY,
})
```

Completeness check (lines 262–277):
```python
has_entry = bool(types & _ENTRY_EVENTS)
has_exit = bool(types & _EXIT_EVENTS)
has_action = bool(types & _ACTION_EVENTS)

if has_entry and has_exit and has_action:
    completeness = StoryCompleteness.COMPLETE
```

**COMPLETE requires all three.** Any track missing any one category is not COMPLETE.

---

## Part F: S07 Event Type → StoryBuilder Category Mapping

Verified from live pipeline run (232 actual events):

| S07 Event Type | Count | ENTRY? | ACTION? | EXIT? | Roled? |
|---|---:|---|---|---|---|
| `cycling` | 129 | NO | **NO** | NO | ❌ **UNROLED** |
| `person_entered_scene` | 21 | **YES** | NO | NO | ✓ |
| `person_left_scene` | 20 | NO | NO | **YES** | ✓ |
| `light_turned_on` | 10 | NO | NO | NO | ❌ UNROLED |
| `person_reaching_up` | 9 | NO | NO | NO | ❌ UNROLED |
| `light_turned_off` | 8 | NO | NO | NO | ❌ UNROLED |
| `vehicle_approaching` | 6 | NO | **YES** | NO | ✓ |
| `vehicle_receding` | 6 | NO | **YES** | NO | ✓ |
| `person_crouching_sustained` | 4 | NO | NO | NO | ❌ UNROLED |
| `person_sitting` | 3 | NO | NO | NO | ❌ UNROLED |
| `vehicle_stationary` | 3 | NO | **YES** | NO | ✓ |
| `person_standing_up` | 2 | NO | NO | NO | ❌ UNROLED |
| `running` | 2 | NO | NO | NO | ❌ UNROLED |
| `walking_upstairs` | 2 | NO | NO | NO | ❌ UNROLED |
| `walking_downstairs` | 2 | NO | NO | NO | ❌ UNROLED |
| `group_gathering` | 1 | NO | NO | NO | ❌ UNROLED |
| `person_picked_up_book` | 1 | NO | NO | NO | ❌ UNROLED |
| `person_placed_handbag` | 1 | NO | NO | NO | ❌ UNROLED |
| `person_fallen` | 1 | NO | NO | NO | ❌ UNROLED |
| `person_crawling` | 1 | NO | NO | NO | ❌ UNROLED |

**Roled events (21+20+6+6+3 = 56 of 232 = 24.1%)**
**Unroled events (176 of 232 = 75.9%)**

**Notable missing mappings:**
- `running` → should logically be an ACTION (it IS `EventType.PERSON_RUNNING` but the narrative builder emits it as `"running"`, not `"person_running"`)
- `walking_upstairs` / `walking_downstairs` → should logically be ACTIONs
- `cycling` → should logically be an ACTION
- `person_sitting` → should logically be an ACTION or posture event
- `person_crouching_sustained`, `person_fallen`, `person_crawling` → security/safety events — arguably ACTIONs

### The `running` / `person_running` Mismatch

This is a critical sub-finding:

`_ACTION_EVENTS` includes `EventType.PERSON_RUNNING = "person_running"`.
The narrative builder at S07 line 735 emits `event_type=activity.label` where `activity.label = "running"` (not `"person_running"`).

**`"running"` ≠ `"person_running"`**

So even if a track is correctly classified as running by `ActivityClassifier`, the emitted event type is `"running"` which is NOT in `_ACTION_EVENTS` (`"person_running"` is). This is a type-string mismatch between Pass 7 and `_ACTION_EVENTS`.

---

## Part G: S08 → S09 Event Count Integrity

| Metric | Value |
|---|---|
| S07 output events | 232 |
| S08 fused events | 232 (0 discarded) |
| S09 events covered | **232** |
| Event loss | **0** |

No events are lost between S07 and S09. S08 attaches confidence scores and passes all events through. S09 receives the full 232 events.

**The zero-complete-stories problem is not caused by event loss.**

---

## Part E: Real Candidate Story Chains

Investigated top 15 tracks by event count. All confirmed.

### Tracks that would be COMPLETE if `cycling` were an ACTION

| Track | Duration | Events | Entry? | Cycling? | Exit? | S09 actual | Would be |
|---|---|---|---|---|---|---|---|
| 160 | 12.3s | 3 | ✓ 02:15 | ✓ 02:15 | ✓ 02:28 | PARTIAL | COMPLETE |
| 177 | 11.0s | 3 | ✓ 02:20 | ✓ 02:20 | ✓ 02:31 | PARTIAL | COMPLETE |
| 234 | 5.2s | 3 | ✓ 02:41 | ✓ 02:41 | ✓ 02:47 | PARTIAL | COMPLETE |
| 252 | 9.3s | 3 | ✓ 03:22 | ✓ 03:22 | ✓ 03:31 | PARTIAL | COMPLETE |
| 273 | 5.2s | 3 | ✓ 03:40 | ✓ 03:40 | ✓ 03:45 | PARTIAL | COMPLETE |
| 366 | 0.5s | 3 | ✓ 04:06 | ✓ 04:06 | ✓ 04:06 | PARTIAL | COMPLETE |
| *(+4 more)* | — | — | — | — | — | — | — |

**10 tracks globally would be classified COMPLETE** if `cycling` were added to `_ACTION_EVENTS`.

### Selected chain examples — exact S07→S09 trace

#### Track 160 (duration=12.3s, obs=45)

```
02:15  person_entered_scene   conf=0.811   role=ENTRY   rule=activity_state_machine
02:15  cycling                conf=0.804   role=—       rule=narrative_builder
02:28  person_left_scene      conf=0.811   role=EXIT    rule=activity_state_machine
```

S09 result: **PARTIAL (entry+exit, no action)**
Missing: action event
Reason: `cycling` is not in `_ACTION_EVENTS`
Would be COMPLETE: **YES** (entry ✓, exit ✓, cycling as action ✓)

#### Track 252 (duration=9.3s, obs=7)

```
03:22  person_entered_scene   conf=0.757   role=ENTRY   rule=activity_state_machine
03:22  cycling                conf=0.756   role=—       rule=narrative_builder
03:31  person_left_scene      conf=0.757   role=EXIT    rule=activity_state_machine
```

S09 result: **PARTIAL (entry+exit, no action)**
Identical pattern. This is the canonical track template for all 10 would-be-complete tracks.

#### Track 289 (vehicle track, duration=1.2s)

```
03:53  vehicle_approaching    conf=0.682   role=ACTION  rule=rule_vehicle_approaching
03:53  vehicle_receding       conf=0.679   role=ACTION  rule=rule_vehicle_receding
03:53  vehicle_stationary     conf=0.680   role=ACTION  rule=rule_vehicle_stationary
```

S09 result: **PARTIAL (has action, no entry, no exit)**
This vehicle track has 3 ACTION events but no ENTRY or EXIT. Vehicles don't get `person_entered_scene` / `person_left_scene`. The rule engine generates vehicle events but no vehicle-specific entry/exit events are defined.

#### Track 1 (duration=12s, 12 events — OBS-003 track)

```
00:00  person_reaching_up     conf=0.870   role=—       rule=narrative_builder
00:01  person_entered_scene   conf=0.880   role=ENTRY   rule=activity_state_machine
00:01  cycling                conf=0.870   role=—       rule=narrative_builder
00:08  person_reaching_up     conf=0.880   role=—       rule=narrative_builder
00:11  person_reaching_up     conf=0.880   role=—       rule=narrative_builder
00:13  person_left_scene      conf=0.874   role=EXIT    rule=activity_state_machine
00:16  person_reaching_up     conf=0.880   role=—       rule=narrative_builder
00:21  person_reaching_up     conf=0.880   role=—       rule=narrative_builder
00:27  person_reaching_up     conf=0.874   role=—       rule=narrative_builder
00:41  person_reaching_up     conf=0.880   role=—       rule=narrative_builder
00:48  person_reaching_up     conf=0.859   role=—       rule=narrative_builder
00:53  person_reaching_up     conf=0.878   role=—       rule=narrative_builder
```

S09 result: **PARTIAL, is_coherent=False** (OBS-003 segment)
Events after `person_left_scene` at 00:13 → `person_reaching_up` events from 00:16 to 00:53.
This is the source of the continuity issue (see Part H).

---

## Part H: OBS-003 — Continuity Issue Investigation

**Segment:** `seg_1_e9932991`  
**Track ID:** 1  
**Event count:** 12  
**Completeness:** PARTIAL  
**is_coherent:** False  
**Continuity issues:** 5

### The Issues (verbatim from ContinuityChecker)

```
Event 7 (person_reaching_up) follows terminal event (person_reaching_up) — track 1
Event 8 (person_reaching_up) follows terminal event (person_reaching_up) — track 1
Event 9 (person_reaching_up) follows terminal event (person_reaching_up) — track 1
Event 10 (person_reaching_up) follows terminal event (person_reaching_up) — track 1
Event 11 (person_reaching_up) follows terminal event (person_reaching_up) — track 1
```

**Wait — the log says "follows terminal event (person_reaching_up)"** but `person_reaching_up` is NOT in `_TERMINAL_EVENTS`. This is a bug in the error message — it prints `prev_event.event_type` which was `person_reaching_up` because `person_left_scene` set `seen_terminal=True`, and then subsequent events all reference the wrong "prev_event" in the message format.

### Actual chain of errors

Source: [`continuity.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/engines/temporal/story_preservation/continuity.py) lines 83–91:

```python
if seen_terminal:
    issues.append(
        f"Event {i} ({event.event_type}) follows terminal event "
        f"({prev_event.event_type}) — track {event.track_id}"
    )
if prev_event.event_type in _TERMINAL_EVENTS:
    seen_terminal = True
```

**Event 6 is `person_left_scene` at 00:13.** After processing event 6:
- `prev_event.event_type = "person_left_scene"` → sets `seen_terminal = True`
- Events 7–11 are `person_reaching_up` at 00:16–00:53
- For each: `seen_terminal=True` → issue generated

**Why do events 7–11 exist after the exit?**

Because narrative_builder (Pass 7) generates events for the **full track duration**. Track 1 has observations from 00:00 to ~00:53 (duration 12s). The activity state machine generates `person_left_scene` when the person reaches the edge or the track ends. But the narrative builder generates `person_reaching_up` for every individual gesture detected during the track's full lifespan.

The result: `person_left_scene` is generated at 00:13 (when person reaches an edge), but the tracker continues tracking the person until 00:53. The later `person_reaching_up` events from the narrative builder cover the full 0–53s span.

### OBS-003 Classification

**Genuine StoryBuilder + continuity checker defect — not isolated.**

Two contributing causes:
1. **ContinuityChecker:** Once `seen_terminal=True` after `person_left_scene`, any subsequent event is flagged. But in a real video, a long track can have the person appear near an edge (triggering exit event) and then continue moving. The tracker doesn't stop; neither should the continuity checker block all subsequent events.
2. **Event ordering across generators:** The narrative builder generates events covering the full track span without respect to the exit event position. This creates real (not artificial) events after `person_left_scene`.

**Is OBS-003 related to FAIL-008?** No, directly. Track 1 is PARTIAL regardless of the continuity issue, because cycling is not an action. The continuity issue reduces Track 1's narrative score but doesn't determine its completeness.

**Is OBS-003 an isolated edge case?** Yes, in the 300s run — only 1 segment has continuity issues. But the root cause (narrative builder events spanning after exit events) could appear in any long track with an early-exit event.

---

## Summary: Why Zero Complete Stories

There are **two independent root causes** both of which must be fixed:

### Root Cause 1 — Missing event type in `_ACTION_EVENTS` (PRIMARY)

`cycling` is generated for 83.8% of confirmed person tracks but is NOT in StoryBuilder `_ACTION_EVENTS`.

Result: Tracks with `person_entered_scene + cycling + person_left_scene` = **PARTIAL**, not COMPLETE.

**This alone explains FAIL-008.**

Additionally, `running` is emitted as `"running"` but `_ACTION_EVENTS` contains `"person_running"`. These two type strings do not match. Running events cannot qualify as ACTIONs.

### Root Cause 2 — Activity state machine emits no intermediate action events (SECONDARY)

The activity state machine produces `person_entered_scene` and `person_left_scene` but does NOT explicitly emit a `person_walking` event when the track transitions through WALKING state.

Checking the state machine output for 154 confirmed person tracks — none of them have `person_walking`, `person_standing`, or `person_loitering` events. This means even if Root Cause 1 were fixed, tracks that were NOT classified as cycling would still have PARTIAL stories (entry+exit, no action from state machine).

The state machine transitions through WALKING internally but the transition event it emits is `person_entered_scene` (not `person_walking`). Whether the state machine emits a `person_walking` event when transitioning INTO walking state requires further code inspection of the full state machine implementation.

---

## Recommended Fixes (NOT IMPLEMENTED in Phase 6C)

### Fix 1: Add `cycling` and activity-classifier labels to `_ACTION_EVENTS`

**In [`story_builder.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/engines/temporal/story_preservation/story_builder.py) lines 56–61:**

```python
# Current:
_ACTION_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_WALKING, EventType.PERSON_RUNNING,
    EventType.PERSON_STANDING, EventType.PERSON_LOITERING,
    EventType.VEHICLE_APPROACHING, EventType.VEHICLE_RECEDING,
    EventType.VEHICLE_STATIONARY,
})

# Recommended:
_ACTION_EVENTS: frozenset[str] = frozenset({
    EventType.PERSON_WALKING, EventType.PERSON_RUNNING,
    EventType.PERSON_STANDING, EventType.PERSON_LOITERING,
    EventType.VEHICLE_APPROACHING, EventType.VEHICLE_RECEDING,
    EventType.VEHICLE_STATIONARY,
    # Activity classifier labels (narrative_builder outputs)
    "cycling", "running", "walking_upstairs", "walking_downstairs",
    # Posture/safety events
    "person_sitting", "person_crouching_sustained",
    "person_fallen", "person_crawling",
    "person_reached_up", "person_reaching_up",
})
```

**Predicted effect:** 10 tracks become COMPLETE immediately. Others may also become complete if `running`, `person_sitting` etc. now qualify.

### Fix 2: Align `running` event type string

**In [`activity_classifier.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/utils/activity_classifier.py) OR in `_ACTION_EVENTS`:**

The narrative builder emits `event_type = activity.label` where `label = "running"`. But `_ACTION_EVENTS` contains `EventType.PERSON_RUNNING = "person_running"`. Fix by adding `"running"` to `_ACTION_EVENTS` (Fix 1 covers this) or normalizing the label in Pass 7.

### Fix 3: ContinuityChecker `seen_terminal` scope

**In [`continuity.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/engines/temporal/story_preservation/continuity.py) lines 83–91:**

The check `if seen_terminal` should only fire for events that logically require the actor to still be present (walking, running, standing). Lighting events (`light_turned_on`), narrative events, or pose events generated retrospectively should be exempt.

Alternatively: the narrative builder should clip events to the track's confirmed observation window before `person_left_scene`.

**Scope: isolated to long tracks with early exit events. Low priority.**

---

## Final Answers

**Q2: Why are there zero COMPLETE stories?**

Because `cycling` — which is emitted for 83.8% of confirmed person tracks — is not in `_ACTION_EVENTS`. The StoryBuilder requires ENTRY + ACTION + EXIT. Tracks that have `person_entered_scene + cycling + person_left_scene` are classified PARTIAL because cycling is not recognized as an action.

A secondary cause: `running` is emitted with the wrong type string (`"running"` vs `"person_running"`). Other activity types (`walking_upstairs`, `walking_downstairs`, `person_sitting`, `person_crouching_sustained`) are also unroled.

**Q3: Is FAIL-008 a genuine StoryBuilder defect?**

**YES.** `_ACTION_EVENTS` was defined without including the event types that `ActivityClassifier` (Pass 7 narrative builder) actually emits. This is a mismatch between the event vocabulary of the classifier and the completeness logic of the StoryBuilder. The two components were not integrated consistently.

**Q4: Is OBS-003 related to the same root cause?**

**NO, directly.** OBS-003 is a separate issue — `ContinuityChecker` flags events after a terminal event (`person_left_scene`) even when the track continues being observed and narrative events are generated retrospectively. Root cause is different but also a genuine defect.
