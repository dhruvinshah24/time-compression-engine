# Phase 6D.5 — Complete Story Visual Validation Report

**Phase:** 6D.5  
**Baseline commit:** `c1351c6`  
**Previous experiment:** Phase 6D.4 (300s rerun, 10 complete stories)  
**Date:** 2026-09-13  
**Type:** Visual audit — NO production code changes  

---

## 1. Objective

Determine whether the 10 structurally complete stories from Phase 6D.4 represent genuinely correct, observable actions. This is a precondition for the 595s validation run.

Methodology: Extract representative frames at mid-point of each target track's activity interval. Classify each visually: GENUINE_ACTION | NOT_ACTION | AMBIGUOUS | NOT_VERIFIABLE.

---

## 2. Baseline Commit

`c1351c6` — Phase 6D.4 vocabulary alignment.  
Story completeness: 1 → 10 (running × 4, walking_upstairs × 4, cycling × 1, mixed × 1).

---

## 3. Stories Inspected

Five stories prescribed by Phase 6D.5 mandate:

| Track | Predicted action | Timestamp | Duration | obs_count | Frames inspected |
|---|---|---|---|---|---|
| 56  | `running`          | 00:44–01:00 | 16.2s | 43 | f01329, f01557, f01630 |
| 160 | `running`          | 02:16–02:28 | 12.4s | 45 | f04084, f04254, f04310 |
| 366 | `running`          | 04:06      | 0.5s  | 3  | f07389, f07382, f07384 |
| 14  | `walking_upstairs` | 00:30–00:38 | 8.2s  | 28 | f00929, f01037, f01074 |
| 177 | `walking_upstairs` | 02:20–02:31 | 11.0s | 27 | f04229, f04380, f04429 |

Additional tracks inspected per mandate:

| Track | Predicted action | Role |
|---|---|---|
| 234 | `cycling` | Known false positive — Phase 6D.1 confirmation |
| 1   | `walking_upstairs` | OBS-003 continuity defect track |

---

## 4. Visual Results

### Track 56 — predicted: `running`

**Frames:** f01329 (00:44), f01557 (00:51), f01630 (00:54)  
**Scene:** Indoor hospital room. A doctor wearing a stethoscope is leaning over a patient in bed. A nurse stands nearby.

- No person is running in any frame.
- The high-speed detection (`mean_speed=0.378`) is tracking a close-up indoor camera shot; rapid motion is due to cut/camera change, not a running person.
- **Classification: NOT_ACTION**
- Rationale: Doctor examining patient. Absolute absence of running gait. High bbox velocity plausibly from camera cut or zoom, not locomotion.

---

### Track 160 — predicted: `running`

**Frames:** f04084 (02:16), f04254 (02:21), f04310 (02:23)  
**Scene at f04084:** A traffic police officer standing in an intersection, arms outstretched directing traffic. City street, 1940s cars.  
**Scene at f04254, f04310:** An overhead/bird's-eye shot of a sidewalk. Human silhouettes visible from directly above, standing and walking at normal pace.

- No person is running in any frame.
- At f04084: officer is stationary. At f04254–f04310: pedestrians are standing or walking slowly, viewed from overhead.
- The high speed metric is likely an artifact of camera angle change between adjacent observations (outdoor ground-level → overhead angle cut).
- **Classification: NOT_ACTION**
- Rationale: Standing officer and slow-moving overhead pedestrians. No running observable.

---

### Track 366 — predicted: `running`

**Frames:** f07389, f07382, f07384 (all at 04:06)  
**Scene:** Overhead/bird's-eye view of a street intersection. A small human figure visible at top-right walking on a sidewalk. Cars parked and moving in street.  
**Note:** Track 366 has only 3 observations over 0.5 seconds — the minimum threshold for the `running` label. This is an extremely short track.

- No person is visibly running.
- The figure appears to be walking normally on a sidewalk in an overhead shot. The 3-observation window is insufficient to distinguish running from normal gait.
- `mean_speed=0.128` is below what would be expected for actual running at this camera distance.
- **Classification: NOT_ACTION**
- Rationale: Short-duration overhead detection. Person walking on sidewalk. Classifier fired on minimal data (3 obs, 0.5s).

---

### Track 14 — predicted: `walking_upstairs`

**Frames:** f00929 (00:31), f01037 (00:34), f01074 (00:35)  
**Scene:** Outdoor street setting. Two police officers in uniform standing near the rear of an ambulance vehicle. In f01037 and f01074, they appear to be loading or handling something at the vehicle's rear door.

- No stairs visible in any frame.
- No upward vertical movement observable.
- `mean_vy = -0.023` (slightly negative = centroid moving upward in image) accounts for the stair detection signal, but this is consistent with camera angle or the officers crouching/loading.
- High `mean_speed=0.395` is from horizontal traversal across the scene (ambulance context), not stair climbing.
- **Classification: NOT_ACTION**
- Rationale: Officers loading ambulance at street level. No stairs present or visible.

---

### Track 177 — predicted: `walking_upstairs`

**Frames:** f04229 (02:21), f04380 (02:26), f04429 (02:27)  
**Scene:** Overhead/aerial-angle shot of a sidewalk (same overhead scene as Track 160, different time window). Pedestrian silhouettes visible from directly above, walking or standing on the sidewalk.

- No stairs visible in any frame.
- Overhead camera angle creates sustained negative mean_vy (centroid moves toward top of frame = away from camera = classifier interprets as "moving upward").
- This is the stair detection false positive pattern: overhead shots produce systematic upward vertical velocity that the stair classifier mistakes for stair climbing.
- **Classification: NOT_ACTION**
- Rationale: Pedestrians walking on level sidewalk viewed from above. Upward centroid movement is a camera angle artifact, not stair climbing.

---

## 5. Structural Results

Per-story structural analysis (entry → action → exit temporal ordering):

| Track | Entry event | Action event | Exit event | Same track | Temporal order | Action inside interval | Non-null evidence | Continuity break |
|---|---|---|---|---|---|---|---|---|
| 56  | person_entered_scene | running | person_left_scene | ✅ | ✅ | ✅ | ✅ | None |
| 160 | person_entered_scene | running | person_left_scene | ✅ | ✅ | ✅ | ✅ | None |
| 366 | person_entered_scene | running | person_left_scene | ✅ | ✅ | ✅ | ✅ | None (3 obs, borderline) |
| 14  | person_entered_scene | walking_upstairs | person_left_scene | ✅ | ✅ | ✅ | ✅ | None |
| 177 | person_entered_scene | walking_upstairs | person_left_scene | ✅ | ✅ | ✅ | ✅ | None |

**Structural validity: STRUCTURALLY_VALID for all 5.** The StoryBuilder correctly assembles the event chains in the right order. The defect is entirely semantic — the classifier fires on the wrong physical phenomenon.

---

## 6. Separation of Structural and Semantic Validity

| Track | Predicted action | Story complete | Structure valid | Action visually valid | Result |
|---|---|---|---|---|---|
| 56  | running | YES | STRUCTURALLY_VALID | NOT_ACTION (doctor at bedside) | **SEMANTIC FAIL** |
| 160 | running | YES | STRUCTURALLY_VALID | NOT_ACTION (officer + overhead pedestrians) | **SEMANTIC FAIL** |
| 366 | running | YES | STRUCTURALLY_VALID | NOT_ACTION (overhead sidewalk figure, 3 obs) | **SEMANTIC FAIL** |
| 14  | walking_upstairs | YES | STRUCTURALLY_VALID | NOT_ACTION (officers at ambulance) | **SEMANTIC FAIL** |
| 177 | walking_upstairs | YES | STRUCTURALLY_VALID | NOT_ACTION (overhead pedestrians) | **SEMANTIC FAIL** |

**Summary:**
- Structural validity: 5/5 VALID
- Semantic validity: **0/5 GENUINE_ACTION**
- not_action: 5
- ambiguous: 0
- not_verifiable: 0

This is the same failure pattern as Phase 6D.1 (cycling): the StoryBuilder produces structurally correct chains, but the upstream classifiers produce semantically incorrect action labels.

---

## 7. Key Failure Patterns Identified

### Pattern A — `running` from indoor camera cuts

Track 56: hospital interior. High `mean_speed` (0.378) is caused by rapid camera motion or cut, not a running person. The doctor-at-bedside sequence involves close-up camera work that produces high centroid displacement across frames despite no locomotion. The running classifier uses a velocity threshold without verifying that the person is locomoting rather than the camera moving.

### Pattern B — `walking_upstairs` from overhead camera angle

Tracks 177 and 160 (and Track 14 to a lesser extent): overhead shots produce a sustained negative `mean_vy` (centroid moves toward top of image = "moving upward" in image coordinates). The stair detector uses sustained upward centroid movement as its primary signal. This is a systematic false positive for any overhead camera angle: **level walking viewed from above is indistinguishable from stair climbing by centroid vy alone.**

### Pattern C — `running` from minimal observations

Track 366: only 3 observations over 0.5s. The classifier returns `"running"` based on speed threshold alone with essentially no temporal evidence. Single-cut detections in aerial shots can trivially exceed the threshold.

### Pattern D — `walking_upstairs` from ambulance-loading scene

Track 14: officers loading the ambulance rear. The slight upward centroid movement and horizontal traversal produce stair-detection confidence. No stairs present.

---

## 8. Cycling Status (Track 234)

**Track 234 mid frame (02:44, frame 4927):**  
Scene: A man in a long coat walking outdoors, suburban setting with a low stone wall and shrubbery behind him. No bicycle visible. No cycling motion observable.

- **Confirmed: NOT_CYCLING** — same as Phase 6D.1 visual audit.
- The Phase 6D.4 run still produces this track as `cycling` (conf=0.813).
- The experimental threshold (0.25) and temporal alignment were not sufficient to suppress this track. Track 234 still passes both the bicycle proximity signal and the velocity signal at the 0.25 threshold.

Cycling status: **UNVALIDATED**  
Candidates: 2 (tracks 234, 254)  
Genuine: 0 | Not_cycling: 2 | Ambiguous: 0 | Not_verifiable: 0  
**No positive cycling ground truth was observed in this footage.**

---

## 9. OBS-003 Status (Track 1)

**Track 1 frames (00:01–00:07):**  
Both frames show the animated title card — "When YOU are a Pedestrian" — with stylized silhouette figures of a police officer and running/walking children. This is **a graphic illustration, not a real person**.

The story seg_1 is classified COMPLETE because:
- `person_entered_scene` (detected on title card animation start)
- `walking_upstairs` (centroid of animated figure moves upward as it's drawn)
- `person_left_scene` (animation ends and frame cuts to live footage)

OBS-003 continuity issues: **5 events** in this segment — `person_reaching_up` events continue to fire after `person_left_scene` (same track, later in video at hospital scenes).

**OBS-003 assessment:** The continuity issue is real but the underlying problem is worse than documented — seg_1 itself should be invalid because it tracks animated title card graphics, not a real person. This is a separate issue from OBS-003 (which is about post-exit events). OBS-003 remains DEFERRED, but this adds a new concern: **person tracking on non-person objects** (animated graphics). Not fixed in this phase.

---

## 10. Failure Observations Summary

| Failure | Type | Cause | Affected tracks |
|---|---|---|---|
| `running` on indoor camera motion | Semantic FP | Velocity threshold doesn't distinguish camera motion from body locomotion | 56 |
| `running` on overhead pedestrian | Semantic FP | Aerial view + short track (3 obs) | 366, 160 |
| `walking_upstairs` on overhead shot | Semantic FP | Overhead camera angle → systematic upward vy | 177, 160 |
| `walking_upstairs` on ambulance loading | Semantic FP | Centroid vy triggered by bending/crouching | 14 |
| `cycling` on outdoor walking | Semantic FP | Bicycle proximity + velocity threshold | 234 |
| Story complete from animated title card | Semantic FP | Graphic tracked as person | 1 |

---

## 11. Limitations

1. **Sample size = 5** stories. This is a spot-check, not a systematic evaluation. There may be genuine running or stair-climbing events elsewhere in the video that are correctly classified but not sampled here.

2. **Single mid-point frame per track** was examined for shorter tracks (366, 14). For longer tracks (56, 160, 177), 3 frames were examined. Borderline cases where the action is visible in only part of the track window cannot be detected.

3. **Generalization is prohibited.** The 0/5 result must not be stated as "running accuracy = 0%". It states: "In this 5-track spot-check, 0 of 5 predicted actions were visually confirmed in archive_001."

4. **Source material is 1948 archival film** with scene types unusual for standard activity classifiers: animated graphics, extreme overhead angles, indoor hospital close-ups, and 1940s street scenes with cameras on vehicles. The classifier was calibrated on contemporary footage patterns.

---

## 12. Decision

**Visual gate: FAIL_VISUAL_GATE**

Gate criterion: ≥ 3/5 stories must be GENUINE_ACTION and STRUCTURALLY_VALID.  
Result: 0/5 GENUINE_ACTION (5/5 STRUCTURALLY_VALID but 5/5 SEMANTIC FAIL).

---

## 13. 595s Status

**595s: BLOCKED**

The visual gate failed. Proceeding to 595s before fixing the identified semantic defects would produce results that cannot be trusted.

---

## 14. Root Cause Diagnosis

Two independent root causes identified:

**ROOT CAUSE R1: Activity classifiers use positional/velocity signals that confound camera motion and scene geometry with body locomotion.**

- `"running"` classifier uses `mean_speed >= RUN_THRESHOLD` without separating camera motion
- `"walking_upstairs"` classifier uses `mean_vy < 0` (upward centroid movement) without verifying camera is horizontal

**ROOT CAUSE R2: No camera-motion compensation in ActivityClassifier.**

Phase 6D.3 added `require_temporal_overlap` (for bicycle proximity signal) and raised `cycle_threshold`. But the core velocity-based labels (`running`, `walking_upstairs`, `walking_downstairs`) have no camera-motion awareness. When the camera pans, zooms, or cuts to an overhead angle, the positional signals are unreliable.

**Note:** Phase 6D.3 already suppressed camera-motion events for cycling via `require_temporal_overlap`. The same principle applies here — but there is no analogous guard for running/stair labels.

**Observation:** Camera motion was detected in S06 for 53 frames in the 300s run:
```
s06_motion_analyze: OK  W=1
  WARN: Camera motion detected in 53 frames.
```
Three tracks were suppressed by camera motion in S07. However, tracks 56, 160, 177, 366 were NOT suppressed — their events were emitted by Pass 7 (narrative_builder), which runs AFTER camera-motion suppression of Pass 1 events. The narrative_builder path bypasses camera-motion filtering.

---

## 15. Recommended Next Experiment

**Phase 6E — Camera-Motion Guard for ActivityClassifier**

Add camera-motion awareness to the narrative_builder pass:

1. Suppress narrative_builder events for person tracks when camera motion is detected during the track's observation window.
2. OR pass `camera_motion_frames` from S06 into S05/ActivityClassifier and zero out velocity measurements on motion-affected frames before computing `mean_speed`.

This must be implemented as a separate named experiment (not a config change) and verified with a controlled 300s rerun before proceeding to 595s.

**Alternative if camera-motion data is unavailable:** Add a minimum observation count guard (e.g., `obs_count >= 10`) before emitting `running` or `walking_upstairs` from narrative_builder. Track 366 (3 obs) and any sub-threshold tracks would be suppressed.

---

## 16. Test Suite

No production code changes were made in Phase 6D.5.  
Full test suite was NOT re-run (no code changes).  
Baseline state: **635 passing, 0 failures** (from Phase 6D.4 commit).
