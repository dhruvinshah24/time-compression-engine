# Phase 6D.2 — ActivityClassifier Cycling Logic Audit

**Phase:** 6D.2  
**Baseline commit:** `bd9d18e`  
**Source file:** [`activity_classifier.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/utils/activity_classifier.py)  
**Date:** 2026-09-06  
**Read from:** actual implementation, not inferred

---

## 1. Module Design Intent vs Actual Scope

The module docstring states it is:

> "Tuned for **indoor CCTV** characteristics: Fixed camera angle (30–60° overhead), controlled lighting, people at distances of 2–15m from camera, Frame skip = 5"

**Actual test footage:** archive_001 — a 1948 *outdoor pedestrian safety film*, 320×240, street-level camera, varying scene types (indoor hospital, street intersections, animated title cards, residential streets). This is a direct mismatch between the design intent and the actual deployment context.

---

## 2. Complete Cycling Logic — Verbatim

### Entry point: `classify()` — lines 98–263

```python
cycling_conf = self._detect_cycling(track, all_tracks or [], mean_speed, mean_h)
...
if cycling_conf >= 0.60:
    return ActivityResult(
        label="cycling",
        confidence=round(cycling_conf, 3),
        ...
        evidence={**evidence, "reason": "bicycle_proximity_or_velocity"},
    )
```

**The decision tree checks cycling FIRST, before stair detection, running, and walking.** Any track where `cycling_conf >= 0.60` is immediately classified as cycling and no other classification is possible.

---

### `_detect_cycling()` — lines 309–361

#### Signal 1: Bicycle Track Proximity

```python
bicycle_tracks = [
    t for t in all_tracks
    if (t.class_name or "").lower() in BICYCLE_CLASSES and t.is_confirmed
]

if bicycle_tracks and track.observations:
    person_cxs = np.array([o.bbox.cx for o in track.observations])
    person_cys = np.array([o.bbox.cy for o in track.observations])

    for bt in bicycle_tracks:
        if not bt.observations:
            continue
        bike_cxs = np.array([o.bbox.cx for o in bt.observations])
        bike_cys = np.array([o.bbox.cy for o in bt.observations])

        dist = np.sqrt(
            (np.mean(person_cxs) - np.mean(bike_cxs)) ** 2
            + (np.mean(person_cys) - np.mean(bike_cys)) ** 2
        )
        if dist < 0.25:
            overlap_conf = max(0.70, 0.95 - dist * 2)
            return overlap_conf
```

**Signal 1 characteristics:**

| Property | Value |
|---|---|
| Trigger condition | Mean centroid distance < 0.25 normalized (25% of frame) |
| Confidence range | 0.70 – 0.95 |
| Time alignment | None — uses mean centroid over full track duration |
| Direction checked | No |
| Class filter | `BICYCLE_CLASSES = {"bicycle", "bike", "cycle", "motorbike", "motorcycle", "scooter"}` |
| Temporal overlap required | No — mean positions compared regardless of frame alignment |
| Person moves with bicycle | Not verified |
| Camera motion considered | No |

**Critical weakness of Signal 1:** The distance is computed between mean centroids across the ENTIRE track duration. A bicycle track that exists anywhere in the 300-second clip and has its mean centroid within 0.25 normalized of a person track's mean centroid will trigger, even if the two tracks never overlap in time. The bicycle track in archive_001 is confirmed in S05 — its mean centroid affects ALL person tracks whose mean centroid falls within the 0.25 radius, regardless of temporal co-location.

#### Signal 2: High Horizontal Speed + Stable Height

```python
if mean_speed >= CYCLE_HORIZ_THRESHOLD:     # 0.018 normalized/s
    heights = [o.bbox.height for o in track.observations]
    height_std = float(np.std(heights))
    if height_std < 0.03:                   # stable seated height
        return 0.65
```

**Signal 2 characteristics:**

| Property | Value |
|---|---|
| Speed threshold | `CYCLE_HORIZ_THRESHOLD = 0.018` normalized units/second |
| Speed metric | `mean_speed = mean(sqrt(dx² + dy²) / dt)` — total vector speed, NOT horizontal only |
| Height stability | `height_std < 0.03` normalized |
| Direction checked | No — uses total 2D speed, not horizontal component |
| Vertical motion considered | Only implicitly (adds to total speed) |
| Camera motion considered | No |
| Object class considered | No — fires on any track passing through classify() |
| Pose information used | No |
| Temporal consistency required | No — a single-frame velocity spike in mean doesn't penalize |
| Minimum observation count | 3 (checked at line 128, returns before Signal 2 for <3 obs) |

---

## 3. Velocity Calculation Units Analysis

```python
self._dt = frame_skip / max(fps, 1.0)
# At frame_skip=5, fps=30: dt = 0.1667 seconds

dx = obs[i].bbox.cx - obs[i - 1].bbox.cx   # normalized [0, 1]
dy = obs[i].bbox.cy - obs[i - 1].bbox.cy   # normalized [0, 1]
vx = dx / self._dt                           # normalized units / second
speed = sqrt(dx² + dy²) / self._dt          # normalized units / second
```

**`mean_speed` is in units of "normalized frame dimensions per second."**

It is NOT in pixels. It IS dependent on `frame_skip` and `fps` (through `dt`). The normalization by `dt` makes it superficially resolution-independent — but `dt` encodes the frame skip rate:

```
At frame_skip=5, fps=30:  dt = 0.167s → threshold = 0.018 normalized/s
At frame_skip=1, fps=30:  dt = 0.033s → threshold = 0.018 normalized/s (same, but each obs covers less time)
```

The threshold value `0.018 normalized/s` is constant regardless of frame_skip. However, **the spatial resolution of each observation changes with frame_skip** — at frame_skip=5, YOLO is running on one of every 5 frames, so each observation covers 5 original frames of motion. A person walking 1 pixel per original frame moves 5 pixels between observations, but the bbox centroid is in normalized coordinates, so resolution matters.

**Resolution dependency:**

```
For a 320×240 frame:
  1 pixel horizontal = 1/320 = 0.003125 normalized units
  0.018 normalized/s × 0.1667s = 0.003 normalized displacement per observation
  = 0.003 × 320px = 0.96 pixels per observation
```

```
For a 1920×1080 frame (HD CCTV):
  0.018 normalized/s × 0.1667s = 0.003 normalized displacement per observation
  = 0.003 × 1920px = 5.76 pixels per observation
```

**At 320×240: 0.96px/observation threshold. At 1920×1080: 5.76px/observation threshold.**

The threshold is NOT resolution-independent. At 320×240, the minimum cycling speed corresponds to sub-pixel detection noise. At 1920×1080, it corresponds to about 1/3 of a step. **The module was calibrated for "indoor CCTV" at higher resolution — the design assumption encoded in `CYCLE_HORIZ_THRESHOLD = 0.018` implicitly requires a resolution much larger than 320×240.**

---

## 4. Critical Design Weaknesses

### W1: Speed is 2D total magnitude, not horizontal

The docstring says "high horizontal speed" but the implementation uses:
```python
speed = sqrt(dx² + dy²) / dt
```
This is the 2D vector magnitude. A nurse's arm swinging vertically contributes the same as horizontal cycling motion. A person walking upstairs (purely vertical) would trigger Signal 2 if their speed exceeds 0.018.

The horizontal component `mean_abs_vx` is computed (line 154) but NOT used in Signal 2.

### W2: No direction consistency requirement

Signal 2 fires on any track where `mean_speed >= 0.018`, regardless of whether the motion is consistently horizontal. A person oscillating left-right (e.g., wiping a table) with `mean_speed >= 0.018` and stable height would trigger. So would a person in an elevator (vertical motion only).

### W3: `height_std < 0.03` is not a cycling indicator at 320×240

At 320×240 resolution, a person's bounding box height ranges from ~10 to ~80 pixels depending on distance. In normalized units:
- Close person (40px tall): height = 0.167 normalized
- Distant person (15px tall): height = 0.063 normalized

For a distant person at ~15px tall: detecting even a ±1px bbox height variation gives `height_std = 1/240 ≈ 0.004` — well under 0.03. Distant persons trivially satisfy `height_std < 0.03` because the detection box is too small for meaningful variance.

This means the "stable seated height" condition is satisfied by every distant/small person in the frame, regardless of posture.

### W4: Signal 1 uses mean centroid without temporal alignment

The bicycle proximity check compares mean centroids across entire track durations. In a 300-second clip, a bicycle track that exists for 10 seconds at position (0.5, 0.5) could trigger Signal 1 for any person whose mean position over 300 seconds is near (0.5, 0.5). The two subjects never need to be in the same frame simultaneously.

### W5: Cycling takes priority over all other classifications

The decision tree checks cycling BEFORE running and walking:
```python
if cycling_conf >= 0.60:
    return ActivityResult(label="cycling", ...)   # exits immediately
# stair, running, walking, standing all checked AFTER
```
A confirmed false-positive from Signal 2 cannot be overridden by a stronger walking or running signal.

### W6: No camera motion compensation

`mean_speed` includes apparent motion caused by camera movement. S06 detects camera motion in 53 frames, but ActivityClassifier has no access to this. A camera pan or shake increases all track speeds simultaneously, triggering Signal 2 universally.

### W7: No minimum track duration for cycling

Signal 2 fires for tracks with as few as 3 observations (the minimum to enter Signal 2). At frame_skip=5, fps=30: 3 observations = 2 intervals × 0.167s = 0.33 seconds. Classifying a 0.33-second track as cycling provides insufficient evidence.

### W8: `BICYCLE_CLASSES` includes motorbikes and scooters

This means any confirmed motorbike or scooter track in S05 would trigger Signal 1 for nearby person tracks, even though the cycling body posture is completely different.

---

## 5. Threshold Analysis at Different Resolutions

| Frame Resolution | CYCLE_HORIZ_THRESHOLD (0.018 n/s) | Pixels/second | Pixels/observation (skip=5, fps=30) | Assessment |
|---|---|---|---|---|
| 320×240 (archive_001) | 0.018 n/s | 5.76 px/s | **0.96 px** | Sub-pixel — fires on noise |
| 640×480 | 0.018 n/s | 11.5 px/s | 1.92 px | Marginal — fires on slow drift |
| 848×480 (design intent) | 0.018 n/s | 15.3 px/s | 2.54 px | Marginal walking threshold |
| 1920×1080 (HD CCTV) | 0.018 n/s | 34.6 px/s | 5.76 px | Reasonable walking minimum |

The threshold was designed for high-resolution indoor CCTV. At 320×240 it becomes sub-pixel.

---

## 6. Summary of Identified Weaknesses

| ID | Weakness | Severity | Effect |
|---|---|---|---|
| W1 | Speed is 2D total, not horizontal-only | HIGH | Arm movements, vertical motion trigger cycling |
| W2 | No direction consistency | HIGH | Oscillatory motion triggers cycling |
| W3 | height_std < 0.03 trivially met at 320×240 | HIGH | All distant persons have stable tiny boxes |
| W4 | Signal 1 no temporal alignment | MEDIUM | Bicycle at frame edge triggers all nearby persons |
| W5 | Cycling has decision-tree priority | MEDIUM | No other label can override a cycling false positive |
| W6 | No camera motion compensation | MEDIUM | Camera shake triggers Signal 2 universally |
| W7 | No minimum duration for cycling | MEDIUM | 0.33-second tracks classified as cycling |
| W8 | BICYCLE_CLASSES includes motorbikes | LOW | Motorbike proximity = cycling classification |
