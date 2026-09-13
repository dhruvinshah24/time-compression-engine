# Phase 6E.3 — Stairs Classifier Implementation Audit

**Phase:** 6E.3  
**Target Module:** `backend/app/utils/activity_classifier.py`  
**Inspected Function:** `ActivityClassifier._detect_stairs(vy_arr, mean_speed)` & decision tree integration  
**Date:** 2026-09-13  

---

## 1. Overview & Location

Stair walking classification is implemented as an internal method of `ActivityClassifier` in `backend/app/utils/activity_classifier.py` (lines 314–355), called by `classify()` at line 215, and evaluated in the decision tree at lines 247–256.

```
classify(track, all_tracks)
   ↓
   vy_arr, mean_speed computed from track.observations
   ↓
   stair_conf, stair_dir = _detect_stairs(vy_arr, mean_speed)
   ↓
   if stair_conf >= 0.55 and mean_speed >= WALK_THRESHOLD:
       return ActivityResult(label=f"walking_{stair_dir}stairs", ...)
```

---

## 2. Velocity Representation & Coordinate Conventions

### Time Step
Extracted frames are spaced by `frame_skip` (default: 5) at video FPS (default: 29.97):
$$\Delta t = \frac{\text{frame\_skip}}{\max(\text{fps}, 1.0)} \approx \frac{5}{29.97} \approx 0.16683\text{ seconds}$$

### Velocity Computation
For consecutive observations $i-1$ and $i$:
$$dx = cx_i - cx_{i-1}, \quad dy = cy_i - cy_{i-1}$$
$$v_x = \frac{dx}{\Delta t}, \quad v_y = \frac{dy}{\Delta t}, \quad \text{speed} = \frac{\sqrt{dx^2 + dy^2}}{\Delta t}$$

**Coordinate Sign Convention:**
Image space coordinates have the origin $(0, 0)$ at the top-left corner:
- $cy$ increases **downward** (toward the bottom of the image).
- $dy < 0 \implies v_y < 0$: centroid moves **upward** in the image (toward the top of the frame).
- $dy > 0 \implies v_y > 0$: centroid moves **downward** in the image (toward the bottom of the frame).

---

## 3. Thresholds & Equations

### Constants
From `activity_classifier.py` lines 54–56:
- `WALK_THRESHOLD = 0.008` (normalized frame units / second)
- `STAIR_VERT_THRESHOLD = 0.005` (normalized frame units / second)

### Mathematical Algorithm in `_detect_stairs()`

1. **Temporal Gate:**
   $$\text{if } \text{len}(vy\_arr) < 4 \implies \text{return } (0.0, \text{"up"})$$
   Because each velocity requires 2 observations, $\text{len}(vy\_arr) = \text{len}(obs) - 1$.
   Therefore, stair detection requires at least **5 observations** ($\text{len}(obs) \ge 5$).

2. **Directional Consistency Counting:**
   $$n_{up} = \sum_{k} \mathbb{I}(vy_k < -0.005)$$
   $$n_{down} = \sum_{k} \mathbb{I}(vy_k > 0.005)$$
   $$n_{total} = \text{len}(vy\_arr)$$

3. **Direction Determination:**
   $$\text{if } n_{up} > n_{down} \implies \text{direction} = \text{"up"}, \quad dominant\_frac = \frac{n_{up}}{n_{total}}$$
   $$\text{else} \implies \text{direction} = \text{"down"}, \quad dominant\_frac = \frac{n_{down}}{n_{total}}$$

4. **Dominance Cutoff:**
   $$\text{if } dominant\_frac < 0.50 \implies \text{return } (0.0, \text{direction})$$

5. **Confidence Scoring:**
   $$mean\_vy\_abs = \frac{1}{n_{total}} \sum_{k} |vy_k|$$
   $$magnitude\_factor = \min\left(1.0, \frac{mean\_vy\_abs}{3 \times 0.005}\right) = \min\left(1.0, \frac{mean\_vy\_abs}{0.015}\right)$$
   $$confidence = 0.6 \times dominant\_frac + 0.4 \times magnitude\_factor$$

6. **Horizontal Locomotion Sanity Check:**
   $$\text{if } mean\_speed < 0.5 \times WALK\_THRESHOLD \ (0.004) \implies confidence = confidence \times 0.5$$

7. **Output Clamping:**
   $$\text{return } (\min(0.93, confidence), \text{direction})$$

---

## 4. Decision Tree Trigger Condition

At line 247:
$$\text{stair\_conf} \ge 0.55 \quad \text{AND} \quad mean\_speed \ge WALK\_THRESHOLD \ (0.008)$$

If satisfied:
- Label assigned: `"walking_upstairs"` or `"walking_downstairs"`.
- This preempts `"running"` (line 259) and `"walking"` (line 270).

---

## 5. Architectural Deficiencies & Vulnerabilities

1. **No Geometry or Viewpoint Awareness:**
   The algorithm assumes the camera is at eye-level or a standard low-angle perspective where vertical motion in image coordinates directly corresponds to vertical motion in physical 3D space. Under an **overhead or elevated downward angle**, forward locomotion on level ground naturally projects onto the vertical image axis ($cy$), causing level walking to register as sustained vertical velocity.

2. **No Population / Scene Normalization:**
   `_detect_stairs()` processes each track in total isolation. It receives only `(vy_arr, mean_speed)`. It has no access to:
   - Concurrent tracks in the same frame/scene.
   - Scene detection boundaries or camera orientation estimates.
   - Mean population vertical drift.

3. **Absence of Bounding Box Posture / Aspect Ratio Signals:**
   Physical stair climbing typically involves cyclical posture cues (leg lift, torso tilt, step cadence). `_detect_stairs()` uses only centroid $cy$ displacement, ignoring bounding box dimensions, aspect ratio variance, and keypoints.

4. **Sensitivity to Moderate Drift:**
   `STAIR_VERT_THRESHOLD = 0.005` is very low. At 320x240 with $\Delta t = 0.1668\text{s}$, a displacement of just 0.2 pixels per extracted frame ($0.2 / 240 / 0.1668 \approx 0.005$) exceeds the threshold. Any pedestrian walking slightly away from or toward an elevated camera trivially exceeds this threshold.
