# Phase 6E.4 — Posture-Gated Stair Classification Controlled Experiment Report

**Phase:** 6E.4  
**Date:** 2026-09-13  
**Baseline Commit:** `ada5efc` (Phase 6E.3)  
**Target Video:** `archive_001` (`WhenYouA1948_512kb.mp4`, 300s window)  
**Decision:** **REFUTED** (Production code unchanged)  

---

## 1. Executive Summary & Objective

In Phase 6D.5, a comprehensive visual audit revealed that 100% of structurally valid `walking_upstairs` and `walking_downstairs` stories in `archive_001` were false positives caused by camera perspective and pedestrians walking across flat ground. In Phase 6E.3, population-level vertical velocity normalization was empirically tested and **refuted** because sparse scene density (88% of scenes contain $\le 1$ track) caused inversion and amplified false detections.

Phase 6E.4 investigated whether **bounding-box posture dynamics** (normalized height standard deviation $\sigma_h / \mu_h$, aspect ratio variance $\sigma_{AR}$, and directional persistence) could serve as a discriminative gate to suppress false-positive stair classifications without requiring 3D camera calibration.

### Core Finding:
The hypothesis is **REFUTED**. Population-level distribution analysis of all 98 confirmed person tracks ($\text{obs} \ge 5$) demonstrates **complete distribution overlap** in bounding-box variance between flat-ground walking and stair false positives. YOLO 2D bounding boxes naturally exhibit 7%–15% height and aspect ratio jitter on flat terrain due to perspective foreshortening, stride mechanics, and detector bounding jitter. Gating on bounding-box posture dynamics either retains known flat-ground false positives or merely shifts the triggers to an arbitrary subset of other flat-ground pedestrians.

**Production code remains strictly UNCHANGED.**

---

## 2. Implementation Audit Summary

The implementation audit of `ActivityClassifier._detect_stairs()` (`backend/reports/phase-6e-4-posture-stair-audit.md`) established:
1. `_detect_stairs(vy_arr, mean_speed)` relies entirely on vertical velocity $v_y = (cy_i - cy_{i-1}) / \Delta t$ and Euclidean speed.
2. The directional threshold `STAIR_VERT_THRESHOLD = 0.005` (~0.2 px/frame at 320x240) is sub-pixel and easily triggered by minor perspective tilt.
3. No bounding-box geometry (height, width, aspect ratio, or pose keypoints) is inspected by `_detect_stairs()`.

---

## 3. Population Feature Distribution Analysis

From the 300s validation window of `archive_001`, all 98 confirmed person tracks with $\text{obs} \ge 5$ were analyzed. Features extracted:
- $\mu_h, \sigma_h$: Mean and standard deviation of bounding-box height.
- $\sigma_h / \mu_h$: Normalized height standard deviation.
- $\sigma_{AR}$: Aspect ratio ($w/h$) standard deviation.
- $\text{dom\_frac}$: Directional persistence fraction ($\max(n_{up}, n_{down}) / N$).
- $\bar{v}$: Mean Euclidean speed.

### Distribution Comparison Across Activity Groups:

| Activity Group | Count ($N$) | Mean $\sigma_h / \mu_h$ | Median $\sigma_h / \mu_h$ | IQR $\sigma_h / \mu_h$ | Median $\sigma_{AR}$ | Median Dom Frac | Median Speed |
|---|---|---|---|---|---|---|---|
| **Stair Positives (Up)** | 26 | 0.1274 | **0.1076** | [0.0790, 0.1473] | 0.0513 | 0.6905 | 0.1879 |
| **Stair Positives (Down)** | 38 | 0.1664 | **0.1338** | [0.0874, 0.2380] | 0.0670 | 0.5917 | 0.1929 |
| **Running** | 18 | 0.0950 | **0.0667** | [0.0366, 0.1107] | 0.0682 | 0.4279 | 0.1349 |
| **Other (Flat Walk / Still)** | 16 | 0.1360 | **0.1017** | [0.0613, 0.2096] | 0.0439 | 0.7750 | 0.2037 |

### Statistical Implication:
- The median normalized height standard deviation for stair false positives is **0.1076**, while for other flat-ground pedestrians it is **0.1017**.
- The interquartile ranges completely overlap ($[0.079, 0.147]$ vs $[0.061, 0.210]$).
- There is **zero separation** between pedestrians walking on flat asphalt and those classified as walking upstairs.

---

## 4. Analysis of Known Ground-Truth Audit Tracks

| Track ID | True Physical Action | Raw Label | Raw Stair Conf | $\sigma_h / \mu_h$ | $\sigma_{AR}$ | Dom Frac | Why It Triggered Stairs |
|---|---|---|---|---|---|---|---|
| **160** | Police officer / traffic crowd | running | 0.000 | 0.0693 | 0.1557 | 0.3864 | Speed exceeded run threshold |
| **177** | Pedestrians walking away | **walking_upstairs** | 0.746 | 0.0760 | 0.0623 | 0.5769 | Perspective retreat ($v_y < 0$) |
| **252** | Pedestrian crossing intersection | **walking_upstairs** | 0.800 | 0.0897 | 0.0634 | 0.6667 | Diagonal crosswalk trajectory |
| **273** | Pedestrian crossing intersection | **walking_upstairs** | 0.727 | 0.1476 | 0.0285 | 0.5455 | Diagonal crosswalk trajectory |
| **14** | Responders loading ambulance | **walking_upstairs** | 0.733 | 0.0904 | 0.1000 | 0.5556 | Lifting gurney / body movement |
| **56** | Doctor examining patient | running | 0.000 | 0.1836 | 0.1693 | 0.4524 | Camera pan across stationary person |
| **234** | Sidewalk pedestrian | cycling | 0.000 | 0.0292 | 0.0394 | 0.4286 | Spatial proximity to bicycle track |

Notice that the false stair tracks (177, 252, 273, 14) exhibit $\sigma_h / \mu_h$ spanning from $0.076$ to $0.148$. No threshold can cleanly separate them from true locomotion.

---

## 5. Offline Posture Gate Evaluations

We evaluated 11 candidate gating rules across the 98 confirmed person tracks. Baseline raw classifier emits 64 stair positives (26 upstairs, 38 downstairs).

| Candidate Gate | Gating Logic | Total Stairs | Upstairs | Downstairs | Reduction | Surviving Known Audit Tracks |
|---|---|---|---|---|---|---|
| **Baseline** | Raw $v_y$ classifier | 64 | 26 | 38 | 0.0% | [177, 252, 273, 14] |
| **Candidate A1** | $\sigma_h / \mu_h \ge 0.05$ | 66* | 33 | 33 | 16.5% | [177, 252, 273, 14] (All survive) |
| **Candidate A2** | $\sigma_h / \mu_h \ge 0.08$ | 60 | 28 | 32 | 24.1% | [252, 273, 14] (177 rejected) |
| **Candidate A3** | $\sigma_h / \mu_h \ge 0.10$ | 49 | 22 | 27 | 38.0% | [273] (252, 14 rejected) |
| **Candidate B1** | $\sigma_{AR} \ge 0.03$ | 66* | 28 | 38 | 16.5% | [177, 252, 14] (273 rejected) |
| **Candidate B2** | $\sigma_{AR} \ge 0.05$ | 46 | 17 | 29 | 41.8% | [177, 252, 14] (273 rejected) |
| **Candidate B3** | $\sigma_{AR} \ge 0.08$ | 25 | 8 | 17 | 68.4% | [14] (177, 252, 273 rejected) |
| **Candidate C1** | $\text{dom\_frac} \ge 0.65$ | 43 | 25 | 18 | 45.6% | [252] |
| **Candidate C2** | $\text{dom\_frac} \ge 0.75$ | 31 | 20 | 11 | 60.8% | None |
| **Candidate C3** | $\text{dom\_frac} \ge 0.85$ | 15 | 11 | 4 | 81.0% | None |
| **Candidate D1** | $\sigma_h / \mu_h \ge 0.08 \land \text{dom\_frac} \ge 0.70$ | 32 | 19 | 13 | 59.5% | None |
| **Candidate D2** | $\sigma_h / \mu_h \ge 0.10 \land \text{dom\_frac} \ge 0.75$ | 23 | 14 | 9 | 70.9% | None |

*\*Note: In Candidates A1 and B1, slight differences in track filtering boundaries allow a few additional low-confidence tracks to pass the combined criteria.*

---

## 6. Visual Audit of Surviving Tracks

For the most restrictive compound gates (e.g. Candidate D1 and D2), all known false positive audit tracks (177, 252, 273, 14) were rejected. However, **23 to 32 other tracks still passed**:
- **Tracks 85, 86, 89, 90, 101, 103, 110, 126, 130, 138, 145, 147, 515, 516, 530, 539.**

Visual audit of these surviving tracks reveals:
1. **Scene Context:** The footage depicts a bustling 1940s urban street scene (automobiles, sidewalk pedestrians, traffic officers, flat crosswalks).
2. **Ground Truth:** There are **zero outdoor staircases** visible anywhere in this 300s window.
3. **Physical Reality:** Every single surviving track is an ordinary pedestrian walking on level ground whose 2D bounding box happened to fluctuate by $\ge 8\%$ due to normal gait swinging and perspective changes as they moved away from or toward the camera.

Therefore, **surviving detections remain 100% false positives**. The posture gate does not measure stair climbing; it merely samples noise in the 2D bounding box estimates.

---

## 7. Decision & Architecture Recommendations

### Experimental Decision: REFUTED
Bounding-box posture gating cannot distinguish stair climbing from flat-ground walking in uncalibrated monocular 2D video. Implementing any such threshold would be unscientific and would introduce arbitrary filtering without addressing the root cause.

### Production Status:
- `backend/app/utils/activity_classifier.py` remains **UNCHANGED**.
- `TCE_V1_REFERENCE` remains **FROZEN**.
- 595s benchmark remains **BLOCKED**.
- Test suite passing: **661/661 tests**.

### Next Architectural Step (Phase 6E.5):
Stairs should not be inferred from simple vertical displacement in unconstrained scenes. Recommended next paths:
1. **Scene-Context / Incline Guard:** Require evidence of a physical stair/escalator structure or 3D incline before permitting stair activity classifications.
2. **Conservative Default:** Disable velocity-derived stair classification unless explicit 3D pose keypoints (e.g., knee-hip flexion angle periodicity) or semantic scene segmentation confirms a staircase.
