# Phase 6E.3 — Population Vertical Velocity Analysis Report

**Phase:** 6E.3  
**Baseline commit:** `0bd6b70`  
**Dataset:** `archive_001` (300s clip, 320x240 @ 29.97fps)  
**Total confirmed person tracks ($\text{obs} \ge 5$):** 98  
**Date:** 2026-09-13  

---

## 1. Objective

Test the hypothesis that population-level vertical velocity across co-occurring tracks in a scene can be used to normalize individual track vertical velocity ($v_y$), suppressing spurious `walking_upstairs` classifications caused by scene geometry (overhead and elevated camera angles).

---

## 2. Methodology

1. Evaluated all 98 confirmed person tracks ($\text{obs} \ge 5$) from the 300s clip.
2. Grouped tracks into scene intervals defined by S03 Scene Change Detection boundaries.
3. For each scene $S$ containing $\ge 2$ tracks, computed:
   $$\text{pop\_mean\_vy} = \frac{1}{N} \sum_{k=1}^N v_{y,k}, \quad \text{pop\_median\_vy} = \text{median}(v_{y,1 \dots N}), \quad \text{pop\_std\_vy} = \text{std}(v_{y,1 \dots N})$$
4. Evaluated three vertical velocity representations against `ActivityClassifier._detect_stairs()`:
   - **Raw $v_y$:** Unmodified individual observation vertical velocities.
   - **Mean-centered $v_y$:** $v_{y, \text{norm}} = v_y - \text{pop\_mean\_vy}$
   - **Median-centered $v_y$:** $v_{y, \text{norm}} = v_y - \text{pop\_median\_vy}$

---

## 3. Scene Population Statistics

Across the entire 300s video (108 detected scene intervals), only 13 scenes contained $\ge 2$ confirmed person tracks with $\ge 5$ observations:

| Scene Index | Extracted Frame Range | Track Count | Population Mean $v_y$ | Population Median $v_y$ | Population Std $v_y$ | Dominant Perspective |
|---|---|---|---|---|---|---|
| Scene 1 | (1, 8) | 5 | +0.00125 | +0.00166 | 0.00311 | Title card silhouettes |
| Scene 13 | (182, 204) | 3 | **-0.02391** | **-0.02266** | 0.00987 | Ambulance loading |
| Scene 43 | (675, 711) | 11 | **-0.15288** | **-0.14048** | 0.15738 | Street pedestrian cluster |
| Scene 44 | (711, 737) | 9 | **-0.08643** | **-0.11466** | 0.09459 | Street crossing |
| Scene 52 | (826, 879) | 4 | **-0.04615** | **-0.05328** | 0.05417 | **Overhead sidewalk (Track 177)** |
| Scene 56 | (891, 896) | 2 | +0.01522 | +0.01522 | 0.06283 | Sidewalk transition |
| Scene 75 | (1204, 1251) | 2 | -0.00833 | -0.00833 | 0.01456 | **Crosswalk (Track 252)** |
| Scene 87 | (1400, 1433) | 12 | -0.01081 | -0.00178 | 0.02748 | Suburban sidewalk |
| Scene 90 | (1479, 1498) | 2 | +0.04287 | +0.04287 | 0.03413 | Street view |
| Scene 96 | (1575, 1596) | 13 | +0.02826 | +0.02442 | 0.03232 | Pathway pedestrians |
| Scene 103 | (1632, 1726) | 12 | +0.06896 | +0.06631 | 0.06120 | Pathway pedestrians |
| Scene 107 | (1760, 1772) | 2 | +0.03699 | +0.03699 | 0.04792 | Street view |
| Scene 108 | (1772, 1776) | 4 | +0.00312 | +0.00312 | 0.01126 | Pathway view |

---

## 4. Normalization Results & Trigger Counts

Evaluating stair walking triggers across all 98 confirmed person tracks:

| Condition | Stair Triggers (Total) | Upstairs Triggers | Downstairs Triggers | Change vs Raw |
|---|---|---|---|---|
| **Raw $v_y$** | **79** | 31 | 48 | Baseline |
| **Mean-centered $v_y$** | **88** | 35 | 53 | **+9 triggers (+11.4%)** |
| **Median-centered $v_y$** | **83** | 32 | 51 | **+4 triggers (+5.1%)** |

**Critical Observation:**
Centering vertical velocity around population mean or median **increased** the total number of stair triggers rather than decreasing them.

---

## 5. Detailed Analysis of Known False-Positive Tracks

| Track ID | Scene ID | Tracks in Scene | Raw $v_y$ | Pop Mean $v_y$ | Norm Mean $v_y$ | Raw Stair Result | Mean-Norm Stair Result | Outcome |
|---|---|---|---|---|---|---|---|---|
| **Track 160** | 49 | **1** | -0.01533 | N/A (single) | N/A | No trigger (conf 0.0) | No trigger (conf 0.0) | **Population unavailable** |
| **Track 177** | 52 | 4 | -0.01777 | -0.04615 | **+0.02838** | `upstairs` (conf 0.746) | **`downstairs` (conf 0.838)** | **FLIPPED to downstairs!** |
| **Track 252** | 75 | 2 | -0.02289 | -0.00833 | **-0.01456** | `upstairs` (conf 0.800) | **`upstairs` (conf 0.800)** | **NOT SUPPRESSED** |
| **Track 273** | 80 | **1** | +0.06244 | N/A (single) | N/A | `upstairs` (conf 0.727) | `upstairs` (conf 0.727) | **Population unavailable** |
| **Track 14** | 13 | 3 | -0.02266 | -0.02391 | **+0.00125** | `upstairs` (conf 0.733) | **`downstairs` (conf 0.733)** | **FLIPPED to downstairs!** |
| **Track 56** | 24 | **1** | -0.02260 | N/A (single) | N/A | No trigger (conf 0.0) | No trigger (conf 0.0) | **Population unavailable** |

---

## 6. Root Causes of Normalization Failure

Three independent mathematical and architectural reasons explain why population normalization failed:

### 1. Inversion of Asymmetry (Sign Flipping)
In scenes with overhead camera angles (such as Scene 52, containing Track 177), all pedestrians have a negative vertical drift in image coordinates ($\text{pop\_mean\_vy} = -0.04615$). Track 177 is walking slightly slower than the population average ($-0.01777$). When the population mean is subtracted:
$$\text{norm\_vy} = -0.01777 - (-0.04615) = +0.02838$$
Because $+0.02838 > \text{STAIR\_VERT\_THRESHOLD} \ (0.005)$, the track still satisfies the stair condition, but now with positive vertical velocity ($v_y > 0$). Consequently, `_detect_stairs()` flips from `walking_upstairs` to `walking_downstairs` with even higher confidence ($0.746 \to 0.838$).

### 2. High Variance in Population Velocities
Pedestrians in natural scenes do not walk at identical speeds or in identical directions. Even on flat sidewalks, people walk in opposite directions (toward and away from the camera). In Scene 52, the standard deviation $\text{std\_vy} = 0.05417$ is larger than the mean itself ($\text{mean\_vy} = -0.04615$). Subtracting a noisy mean across 2–4 tracks adds variance to individual track velocities rather than subtracting a constant drift.

### 3. Population Sparsity in CCTV / Surveillance Video
In typical surveillance video, person tracks rarely appear in large simultaneous crowds within the exact same scene interval. Across 108 detected scene segments in this video:
- 88% of scenes had 0 or 1 confirmed track with $\ge 5$ observations.
- Key false-positive tracks (Track 160, Track 273, Track 56) occurred in scenes where they were the **only** confirmed person track. Population normalization is mathematically undefined when $N=1$.

---

## 7. Conclusion

Population vertical-velocity normalization is **theoretically flawed and empirically refuted** for single-camera surveillance video:
- It creates new false `walking_downstairs` events.
- It fails to eliminate `walking_upstairs` events on remaining tracks.
- It cannot function in single-track scenes.
- It should **NOT** be adopted into the production pipeline.
