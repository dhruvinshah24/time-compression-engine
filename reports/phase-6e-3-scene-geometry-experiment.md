# Phase 6E.3 — Scene-Geometry and Vertical-Velocity Diagnostic Report

**Phase:** 6E.3  
**Baseline commit:** `0bd6b70`  
**Date:** 2026-09-13  
**Status:** COMPLETE — Diagnostic & Controlled Offline Experiment  

---

## 1. Objective

Determine whether population-level vertical velocity across co-occurring tracks in a scene provides a reliable signal for detecting scene geometry (elevated and overhead camera viewpoints) that renders individual person vertical velocity ($v_y$) misleading.

Before adopting any production normalization, rigorously evaluate the hypothesis against empirical track data from `archive_001` (300s).

---

## 2. Baseline Configuration & Constraints

- **Baseline Commit:** `0bd6b70` (Phase 6E.2)
- **Production Code Status:** UNCHANGED.
- **Frozen Configuration:** `TCE_V1_REFERENCE` strictly UNCHANGED.
- **595s Benchmark:** BLOCKED.
- **Active Experimental Parameters:**
  - `min_activity_observations = 5` (KEPT from Phase 6E.2)
  - `cycle_threshold = 0.25`
  - `require_temporal_overlap = True`

---

## 3. Phase 6E.2 Context

Phase 6E.2 successfully resolved short-track instability (`SHORT_TRACK`) by introducing `min_activity_observations = 5`. This suppressed 32 short-track velocity false positives (including Track 366) with zero collateral loss to stair classifications or longer tracks.

However, visual audit of surviving complete stories revealed persistent semantic failures:
- `Track 177` (27 obs) → `walking_upstairs` (NOT_ACTION: overhead sidewalk pedestrians)
- `Track 160` (45 obs) → `running` (NOT_ACTION: overhead perspective & traffic officer)
- `Track 252` (7 obs) → `walking_upstairs` (NOT_ACTION: pedestrian crossing asphalt street)
- `Track 273` (12 obs) → `walking_upstairs` (NOT_ACTION: pedestrian at curb)
- `Track 14` (28 obs) → `walking_upstairs` (NOT_ACTION: police officers loading ambulance)

These tracks have $\ge 5$ observations and cannot be resolved by observation count alone.

---

## 4. Stairs Classifier Implementation Audit Summary

Audit of `ActivityClassifier._detect_stairs()` (`reports/phase-6e-3-stairs-classifier-audit.md`):
- Triggers when $>50\%$ of vertical velocity observations exceed `STAIR_VERT_THRESHOLD = 0.005` (normalized units/s) in one direction, and `mean_speed >= WALK_THRESHOLD (0.008)`.
- Temporal requirement: $\text{len}(vy\_arr) \ge 4 \implies \text{obs\_count} \ge 5$.
- Position, bounding-box posture, and aspect ratio: **COMPLETELY IGNORED**.
- Population and scene context: **COMPLETELY IGNORED**.
- Sensitivity: At 320x240 resolution with $\Delta t = 0.1668\text{s}$, a centroid displacement of only **0.2 pixels** per extracted frame exceeds `STAIR_VERT_THRESHOLD`.

---

## 5. Track-Level & Population-Level Analysis

Evaluated on 98 confirmed person tracks ($\text{obs} \ge 5$) across 108 detected scene segments in `archive_001` (300s):
- Across 108 scenes, only 13 scenes contained $\ge 2$ confirmed person tracks with $\ge 5$ observations.
- 88% of scenes in surveillance footage are sparse ($N \le 1$).
- In scenes with multiple tracks, population vertical velocity ($\text{pop\_mean\_vy}$) varies dramatically:
  - Scene 52 (overhead sidewalk): $\text{pop\_mean\_vy} = -0.04615$, $\text{pop\_std\_vy} = 0.05417$ (4 tracks).
  - Scene 43 (street pedestrian cluster): $\text{pop\_mean\_vy} = -0.15288$ (11 tracks).
  - Scene 103 (pathway pedestrians): $\text{pop\_mean\_vy} = +0.06896$ (12 tracks).

---

## 6. Offline Normalization Test Results

Evaluated three representations across all 98 tracks:

| Condition | Total Stair Triggers | Change vs Baseline |
|---|---|---|
| **Raw $v_y$ (Production)** | **79** | Baseline |
| **Mean-centered $v_y$** | **88** | **+9 triggers (+11.4% ERROR)** |
| **Median-centered $v_y$** | **83** | **+4 triggers (+5.1% ERROR)** |

### Individual Target Track Outcomes Under Normalization:
- **Track 177** (overhead sidewalk): Raw $v_y = -0.01777$ (`upstairs`, conf 0.746). Mean-norm $v_y = +0.02838$ $\implies$ **FLIPPED to `walking_downstairs` (conf 0.838)**.
- **Track 14** (ambulance loading): Raw $v_y = -0.02266$ (`upstairs`, conf 0.733). Mean-norm $v_y = +0.00125$ $\implies$ **FLIPPED to `walking_downstairs` (conf 0.733)**.
- **Track 252** (crosswalk crossing): Raw $v_y = -0.02289$ (`upstairs`, conf 0.800). Mean-norm $v_y = -0.01456$ $\implies$ **STILL fires `walking_upstairs` (conf 0.800)**.
- **Track 160, Track 273, Track 56:** Each was the **only** confirmed person track in its scene. Normalization is undefined ($N=1$).

---

## 7. Critical Safety Test & Positive Ground Truth

- **Comprehensive Search for Genuine Stairs:** Inspected all candidate frames across the entire 300s archive video.
- **Finding:** **"No positive walking-upstairs ground truth available in archive_001."**
  - There are no visible staircases in any inspected scene of `archive_001`.
  - All 79 raw stair triggers are false positives produced by flat-ground walking under angled camera views, diagonal street crossings, or local body motions.
- Normalization cannot be validated for true-positive preservation because zero true positive events exist in this dataset.

---

## 8. Visual Validation of Scene Groups

Inspected high-resolution extracted frames for target scenes:

1. **Scene 52 (Tracks 160 & 177, frames 826–888):**
   - High bird's-eye / overhead angle looking down at pedestrian silhouettes crossing flat concrete.
   - Forward ground walking maps directly onto image $-y$ (upward).
   - Classification: **SCENE_GEOMETRY_CONFIRMED**.
2. **Scene 75 (Track 252, frame 6197):**
   - Frontal eye-level shot of crosswalk. Pedestrian walking diagonally toward background across flat asphalt.
   - Classification: **SCENE_GEOMETRY_CONFIRMED** (perspective foreshortening).
3. **Scene 80 (Track 273, frame 6683):**
   - Pedestrian standing/stepping near street curb. No stair traversal.
   - Classification: **SCENE_GEOMETRY_CONFIRMED**.

---

## 9. Why Population Normalization Failed

1. **Inversion of Velocity Asymmetry:** Subtracting a negative scene drift from a track whose upward speed is lower than average converts its relative velocity into a positive number, artificially generating false `walking_downstairs` events.
2. **High Intra-Scene Variance:** Pedestrians on flat ground walk in opposing directions (toward and away from the camera). The variance within a scene frequently exceeds the mean drift.
3. **Data Sparsity:** 88% of surveillance scenes contain only 0 or 1 person. A population-level adjustment cannot function when $N=1$.

---

## 10. Evaluation of Candidate Fixes (Maximum 3)

### Candidate 1: Aspect Ratio / Bbox Geometry Stair Guard (RECOMMENDED)
- **Hypothesis:** True stair traversal involves body posture changes (stepping cadence, leg lift, vertical compression) that differ from flat-ground walking. Flat-ground walking under overhead cameras exhibits stable bounding box aspect ratios ($\text{width} / \text{height}$) and stable bounding box heights ($\sigma_h / \mu_h$).
- **Mechanism:** Require $\text{height\_std} \ge 0.05$ or aspect ratio variance before stair walking can fire. (On Track 177, $\text{height\_std} = 0.018$ — extremely stable flat walking).
- **Expected Benefit:** Directly suppresses flat-ground overhead walking without relying on population averages or multi-track scenes.
- **False-Negative Risk:** Low on real stairs where cadence causes cyclical height changes.
- **Complexity:** Low (pure track geometry, self-contained in `ActivityClassifier`).

### Candidate 2: Absolute Vertical-to-Horizontal Velocity Ratio Guard
- **Hypothesis:** When walking upstairs/downstairs, vertical movement is accompanied by substantial horizontal step advancement, but on an overhead camera, $v_y$ dominates $v_x$.
- **Mechanism:** Require $|v_y| / (|v_x| + \epsilon) \in [0.3, 2.0]$. Reject tracks with extreme vertical dominance or extreme horizontal dominance.
- **Expected Benefit:** Filters out purely longitudinal camera view tracks.
- **False-Negative Risk:** Moderate (stairs viewed directly from the side have high $v_x$; stairs viewed front-on have high $v_y$).
- **Complexity:** Low.

### Candidate 3: Raising `STAIR_VERT_THRESHOLD` from 0.005 to 0.020
- **Hypothesis:** Current threshold (0.005) is sub-pixel (0.2 px/frame). Raising it to 0.020 (0.8 px/frame) requires genuine, aggressive vertical displacement.
- **Expected Benefit:** Eliminates slight perspective drifts (Tracks 252, 273).
- **False-Negative Risk:** High (might suppress distant genuine stair climbers).
- **Complexity:** Low.

---

## 11. Story Impact

- Because the population normalization hypothesis was **refuted offline**, no production pipeline change was made to vertical velocity calculation.
- The pipeline remains in the Phase 6E.2 state:
  - Complete stories: **8** (all verified long-track arcs).
  - Spurious short-track stories: **0** (Track 366 and Track 75 suppressed).

---

## 12. Remaining Semantic Problems & Root Cause Status

- `SHORT_TRACK`: **RESOLVED** (Phase 6E.2 guard `min_activity_observations = 5`).
- `SCENE_GEOMETRY (OVERHEAD / PERSPECTIVE)`: **UNRESOLVED** (Population normalization refuted; requires track-level geometric posture or cadence gating).
- `BODY_MOTION_CONFUSION (AMBULANCE LOADING)`: **UNRESOLVED** (Track 14).
- `CAMERA_ZOOM_SPEED`: **UNRESOLVED** (Track 56).
- `CYCLING`: **UNVALIDATED** (Track 234).

**Root Cause Status:**
`SCENE_GEOMETRY_NORMALIZATION_REFUTED` — Population-mean vertical velocity does NOT solve scene geometry and introduces inverted downstairs false positives.

---

## 13. Recommended Next Experiment

**Phase 6E.4 — Posture-Gated Stair Classification Experiment**
- Test Candidate 1: Introduce a bounding-box height stability / posture variation gate in `ActivityClassifier._detect_stairs()`.
- Flat-ground walking in overhead views produces highly stable bounding-box dimensions ($\text{height\_std} < 0.03$), whereas stair climbing produces cyclical gait height variations.
- Test whether gating stair detection on posture dynamics eliminates overhead false positives (Tracks 177, 252, 273) in isolated, single-track scenes.
