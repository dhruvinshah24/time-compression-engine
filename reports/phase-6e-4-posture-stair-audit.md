# Phase 6E.4 — Posture & Stair Classification Implementation Audit

**Phase:** 6E.4  
**Target File:** `backend/app/utils/activity_classifier.py`  
**Inspected Methods:** `classify()`, `_detect_stairs()`, `_detect_cycling()`  
**Baseline Commit:** `ada5efc`  
**Date:** 2026-09-13  

---

## 1. Executive Summary

`ActivityClassifier._detect_stairs()` is the subsystem responsible for emitting `walking_upstairs` and `walking_downstairs`. It currently relies **exclusively** on the temporal consistency and magnitude of centroid vertical velocity ($v_y$).

Bounding-box posture metrics (height standard deviation, aspect ratio, width variation) are **not passed** to `_detect_stairs()`. The classifier currently possesses zero posture-awareness for stair walking.

---

## 2. Detailed Input Audit for `_detect_stairs()`

`_detect_stairs()` signature (line 314):
```python
def _detect_stairs(
    self, vy_arr: np.ndarray, mean_speed: float
) -> tuple[float, str]:
```

### Current Inputs:
1. `vy_arr`: 1D NumPy array of instantaneous vertical velocities:
   $$v_{y, i} = \frac{cy_i - cy_{i-1}}{\Delta t}$$
   where $cy$ is the normalized bbox center Y (positive downward) and $\Delta t \approx 0.1668\text{s}$ at 30fps with frame skip 5.
2. `mean_speed`: Scalar Euclidean speed across all observation pairs:
   $$\text{mean\_speed} = \frac{1}{N-1} \sum_{i=1}^{N-1} \frac{\sqrt{(cx_i - cx_{i-1})^2 + (cy_i - cy_{i-1})^2}}{\Delta t}$$

### Feature Availability Audit in `classify()`:

| Feature | Available in `classify()`? | Passed to `_detect_stairs()`? | Currently Used For |
|---|---|---|---|
| `vy_arr` | Yes (line 195) | **YES** | Directional consistency & magnitude |
| `mean_speed` | Yes (line 198) | **YES** | Speed sanity check & walk gate |
| `heights` | Yes (line 206) | **NO** | Min/max/mean computed, passed to `_detect_cycling` |
| `height_mean` | Yes (line 207) | **NO** | Passed to `_detect_cycling` |
| `height_std` | Computed in `_detect_cycling` | **NO** | Cycling seated rider check (`height_std < 0.03`) |
| `bbox.width` | Present on observations | **NO** | Not computed in `classify()` |
| `aspect_ratio` ($w/h$) | Present on observations | **NO** | Not computed in `classify()` |
| `pose keypoints` | Present in S07 Pass 3/5 | **NO** | `ActivityClassifier` does not receive keypoints |

---

## 3. Current Thresholds & Decision Mechanics

1. **Temporal Observation Check:**
   $$\text{len}(vy\_arr) < 4 \implies \text{return } (0.0, \text{"up"})$$
   Requires at least 5 observations ($\text{obs} \ge 5$).

2. **Vertical Velocity Counting:**
   `STAIR_VERT_THRESHOLD = 0.005` (~0.2 px/frame at 320x240):
   $$n_{up} = \sum \mathbb{I}(v_y < -0.005), \quad n_{down} = \sum \mathbb{I}(v_y > 0.005)$$

3. **Dominant Fraction & Cutoff:**
   $$dominant\_frac = \frac{\max(n_{up}, n_{down})}{\text{len}(vy\_arr)}$$
   $$\text{if } dominant\_frac < 0.50 \implies \text{return } (0.0, direction)$$

4. **Confidence Computation:**
   $$magnitude\_factor = \min\left(1.0, \frac{\text{mean}(|v_y|)}{0.015}\right)$$
   $$stair\_conf = 0.6 \times dominant\_frac + 0.4 \times magnitude\_factor$$
   If $\text{mean\_speed} < 0.004$, $stair\_conf \leftarrow stair\_conf \times 0.5$.

5. **Decision Tree Emission (lines 247–256):**
   ```python
   if stair_conf >= 0.55 and mean_speed >= WALK_THRESHOLD:
       label = f"walking_{stair_dir}stairs"
       return ActivityResult(...)
   ```

---

## 4. Why Scene Geometry Bypasses the Current Filter

1. **Sub-pixel threshold:** At $0.005$ frame units/sec, any slight perspective tilt or camera pitch causes ordinary walking away from the camera to register sustained $v_y < -0.005$.
2. **Directional dominance is easily satisfied:** A pedestrian walking in a straight diagonal path across an intersection or sidewalk has $>50\%$ of velocity vectors sharing the same vertical direction.
3. **No posture constraint:** A person walking on flat asphalt in an overhead shot exhibits near-constant bounding box height ($\sigma_h / \mu_h \approx 0.01$ to $0.03$). Stair climbing involves periodic leg elevation, torso compression, and gait cycle dynamics. Because `_detect_stairs()` does not inspect bounding box dynamics, it cannot distinguish flat-ground walking from stair climbing.
