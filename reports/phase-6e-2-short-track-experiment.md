# Phase 6E.2 — Short-Track Activity Classifier Experiment Report

**Phase:** 6E.2  
**Baseline commit:** `c1351c6`  
**Previous experiment commit:** `fae42a9`  
**Date:** 2026-09-13  
**Status:** COMPLETE — Controlled Experiment  

---

## 1. Objective

Determine whether requiring a minimum observation threshold (`min_activity_observations`) before emitting velocity-derived activity labels reduces short-track false positives without incorrectly suppressing sufficiently long, legitimate tracks.

This experiment targets the specific `SHORT_TRACK` failure mode identified in Phase 6E.1 on Track 366 (3 observations over 0.5s triggering `running` via a single noisy centroid displacement).

---

## 2. Baseline Configuration & Constraints

- **Baseline Commit:** `c1351c6`
- **Frozen Configuration:** `TCE_V1_REFERENCE` is strictly UNCHANGED. Default parameter behavior preserves baseline (`min_activity_observations=None` defaults to baseline `min_obs=3`).
- **Pipeline Parameters:** 
  - `model_profile: balanced`, `detection_model: yolo11l`
  - `detection_confidence: 0.25`, `detection_threshold: 0.25`
  - `frame_skip_rate: 5`, `fps: 29.97`
  - `cycle_threshold: 0.25`, `require_temporal_overlap: True` (Phase 6D.3 reference settings)
- **595s Benchmark:** NOT RUN (Blocked pending visual validation).

---

## 3. Phase 6E.1 Evidence Summary

Phase 6E.1 analyzed 5 false complete stories from Phase 6D.5:
- Track 56 (`running`, 43 obs): Camera motion overlap 0.0% → `SCENE_GEOMETRY` (close-up zoom artifact).
- Track 160 (`running`, 45 obs): Camera motion overlap 13.3% → `SCENE_GEOMETRY` (overhead angle).
- Track 366 (`running`, 3 obs): Camera motion overlap 0.0% → `SHORT_TRACK` (instability from minimal data).
- Track 14 (`walking_upstairs`, 28 obs): Camera motion overlap 10.7% → `BODY_MOTION_CONFUSION` (ambulance loading).
- Track 177 (`walking_upstairs`, 27 obs): Camera motion overlap 22.2% → `SCENE_GEOMETRY` (overhead angle).

Camera motion was ruled out as the primary cause (0/5 tracks were in camera-motion frames). Track 366 was isolated as a pure `SHORT_TRACK` failure.

---

## 4. Current Classifier Behavior & Proposed Guard

### Baseline Behavior
In `ActivityClassifier.classify()`:
- `len(obs) < 3`: Returns `entering_scene` (confidence 0.75).
- `len(obs) >= 3`: Computes velocities (`mean_speed`, `mean_vy`, `vy_arr`).
  - Stair detection requires `len(vy_arr) >= 4` (`obs_count >= 5`).
  - Running detection checks `mean_speed >= RUN_THRESHOLD` (0.022) with **no minimum observation count**.
  - A track with exactly 3 observations (2 velocity pairs) over 0.5s is eligible for `running`. If one displacement exceeds the threshold due to jitter or camera cut, `running` fires with high confidence.

### Experimental Parameter Insertion Point
The guard was inserted directly into `ActivityClassifier` (`backend/app/utils/activity_classifier.py`) and exposed via `s05_track.py`:
- `__init__(..., min_activity_observations: Optional[int] = None)`
- Default `None` defaults to baseline `min_obs = 3`.
- In `classify()`:
  - `len(obs) < 2`: Returns `entering_scene` (insufficient points for velocity).
  - `len(obs) < min_obs`: Returns `entering_scene` with provenance metadata (`min_activity_observations`, `reason: below_min_activity_observations`).
- Downstream in `s07_event_understand.py` Pass 7 (`narrative_builder`), `activity.label == "entering_scene"` is not in `activity_event_types`, so no narrative action event is emitted.

---

## 5. Observation-Count Sweep

Measured across all 154 confirmed person tracks from `archive_001` 300s:

| min observations | running candidates | upstairs candidates | downstairs candidates | total velocity candidates | Track 366 suppressed? | tracks removed vs baseline | longest affected obs | shortest surviving obs | median surviving obs |
|---|---|---|---|---|---|---|---|---|---|
| **disabled** (None) | 50 | 26 | 38 | 114 | **NO** (running) | 0 | None | 3 | 6.0 |
| **1** | 62 | 26 | 38 | 126 | **NO** (running) | 0 | None | 2 | 6.0 |
| **3** | 50 | 26 | 38 | 114 | **NO** (running) | 0 | None | 3 | 6.0 |
| **5** | **18** | **26** | **38** | **82** | **YES** (`entering_scene`) | **32** | **4** | **5** | **11.0** |
| **8** | 17 | 13 | 23 | 53 | **YES** (`entering_scene`) | 61 | 7 | 8 | 18.0 |
| **10** | 16 | 10 | 20 | 46 | **YES** (`entering_scene`) | 68 | 9 | 10 | 24.0 |
| **15** | 13 | 7 | 16 | 36 | **YES** (`entering_scene`) | 78 | 13 | 15 | 28.0 |

---

## 6. Track 366 Specific Analysis

- **Track 366 Details:** `obs_count = 3`, `duration = 500.5ms` (frames 1475–1478), `mean_speed = 0.12742`.
- **At baseline (`th=disabled` or `th=3`):** Classified as `running` (conf=0.950). In S09, formed complete story segment `seg_366_731503d8` (`person_entered_scene` → `running` → `person_left_scene`).
- **At experimental `th=5`:** Classified as `entering_scene` (conf=0.750). `running` action suppressed.
- **Track 366 hypothesis outcome:** **CONFIRMED.** Track 366 was an artifact of the `< 3` threshold boundary. Setting `th=5` cleanly suppresses it.

---

## 7. 300s Validation Results (with Selected Threshold `th=5`)

A full end-to-end pipeline run (S01 through S12) was executed with `min_activity_observations=5`:

| Metric | Baseline (6D.4) | Phase 6E.2 (`th=5`) | Delta |
|---|---|---|---|
| Total Confirmed Person Tracks | 154 | 154 | 0 |
| Velocity Activity Candidates | 114 | 82 | -32 (-28.1%) |
| S07 Total Events | 92 | 78 | -14 |
| Story Segments | 148 | 119 | -29 |
| **Complete Stories** | **10** | **8** | **-2** |
| Partial Stories | 30 | 26 | -4 |
| Minimal Stories | 106 | 77 | -29 |
| Exit Only | 1 | 5 | +4 |
| Entry Only | 1 | 3 | +2 |

### Story Completeness Transition Details
- Complete stories dropped from 10 to 8:
  - `seg_366` (Track 366, obs=3): Action `running` suppressed → story transitioned from COMPLETE to partial/entry-exit.
  - `seg_75` (Track 75, obs=3): Action `running` suppressed → story transitioned from COMPLETE to partial.
  - **All other 8 complete stories preserved:** Tracks 1, 14, 56, 160, 177, 234, 252, 273.

---

## 8. Collateral Effects Analysis

- **Collateral Loss on Upstairs/Downstairs:** **0%**. Stair detection (`_detect_stairs()`) requires `len(vy_arr) >= 4` (minimum 5 observations). Setting `min_activity_observations=5` removed exactly 0 upstairs and 0 downstairs tracks.
- **Collateral Loss on Long Running Tracks:** **0%**. Surviving running tracks (e.g. Tracks 56, 160, 189, 202) all have ≥5 observations.
- **Observation length of all 32 suppressed tracks:** Exactly 3 or 4 observations (duration ≤ 0.67s). None of the suppressed tracks represented sustained locomotion.
- **Conclusion:** At `threshold=5`, collateral damage is **zero**.

---

## 9. Visual Audit of Surviving Velocity Activities

Inspected 5 representative surviving velocity-derived activity tracks under `th=5`:

| Track | Action | Obs | Timestamp | Visual Scene | Classification |
|---|---|---|---|---|---|
| **Track 56** | `running` | 43 | 00:44–01:00 | Hospital room, doctor leaning over patient with stethoscope. Camera zoom artifact. | **NOT_ACTION** |
| **Track 160** | `running` | 45 | 02:16–02:28 | Intersection traffic officer and overhead sidewalk pedestrians. Overhead angle. | **NOT_ACTION** |
| **Track 14** | `walking_upstairs` | 28 | 00:30–00:38 | Police officers loading ambulance rear doors at street level. 3D depth motion. | **NOT_ACTION** |
| **Track 177** | `walking_upstairs` | 27 | 02:20–02:31 | Overhead angle of sidewalk pedestrians walking on level ground. Overhead angle. | **NOT_ACTION** |
| **Track 252** | `walking_upstairs` | 7 | 03:22–03:31 | Man in suit walking horizontally across flat street crosswalk. No stairs. | **NOT_ACTION** |

**Visual Audit Outcome:**
- `genuine_action`: 0
- `not_action`: 5
- `ambiguous`: 0
- `not_verifiable`: 0

**Key Finding:** While the observation guard successfully eliminated short-track noise (Track 366 class), the surviving long tracks remain semantically incorrect due to **scene geometry** and **body motion confusion**.

---

## 10. Story Impact

- The reduction in complete stories from 10 to 8 is a **genuine improvement in precision**, not a regression.
- Both eliminated complete stories (Tracks 366 and 75) were 3-observation bursts where a single spurious velocity spike created a complete `entry → running → exit` narrative arc.
- The 8 surviving complete stories are actor arcs with sustained observations (ranging from 7 to 45 observations).

---

## 11. Remaining Semantic Failures

The short-track guard addresses only defect class `SHORT_TRACK`. The remaining semantic failures are:
1. **Scene Geometry — Overhead Perspective (Tracks 160, 177):** Downward camera angles project forward horizontal walking into sustained upward/downward vertical velocity (`vy`), triggering stair classifiers.
2. **Scene Geometry — Close-up / Camera Zoom (Track 56):** In tight indoor shots, camera movement produces high centroid displacement across frames, triggering `running`.
3. **Body Motion / 3D Depth Confusion (Track 14, Track 252):** Bending or walking away from the camera in perspective view creates apparent vertical centroid shifts.
4. **Cycling Unvalidated (Track 234):** Still classified as cycling under proximity/velocity; no ground truth cyclists exist.

---

## 12. Limitations

1. **Absence of Positive Ground Truth:** `archive_001` contains no visually confirmed instances of running, stair-walking, or cycling. We cannot measure true positive recall or sensitivity.
2. **Scope of Fix:** `min_activity_observations` only eliminates short, fleeting tracks (<5 obs). It cannot correct velocity artifacts in tracks with ≥5 observations.

---

## 13. Recommended Next Experiment

**Phase 6E.3 — Population Vertical Velocity Normalization (Scene Geometry Fix)**
- Target: Tracks 177, 160, 252, 273 (stair false positives caused by overhead camera angles).
- Proposed mechanism: In S06/S07, compute the population-mean `vy` across all active tracks in the scene. If population `vy` shows systematic upward drift (indicating an overhead or tilted camera view), subtract the scene drift from individual track vertical velocities before evaluating stair thresholds.

---

## 14. Test Suite

- **Previous Baseline:** 635 passing
- **New Unit Tests Added:** 26 comprehensive tests in `backend/tests/unit/test_phase6e2_short_track_guard.py`
- **Current Total:** **661 passing, 0 failures** (runtime: 13.95s)
