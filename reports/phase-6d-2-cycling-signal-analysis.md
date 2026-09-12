# Phase 6D.2 — Cycling Signal Analysis

**Phase:** 6D.2  
**Baseline commit:** `bd9d18e`  
**Data source:** `results/TCE-v1.0/phase6d2-cycling-track-features.json`  
**Date:** 2026-09-06

---

## 1. Population Overview

Run: archive_001, 300s, YOLO11l, balanced, frame_skip=5, threshold=0.25

| Metric | Value |
|---|---|
| Total tracks (all classes) | 546 |
| Tracks with ≥3 observations (Signal 2 eligible) | 230 |
| Tracks skipped (< 3 obs) | 316 |
| Classified as cycling | **221 / 230 = 96.1%** |
| Not classified as cycling | 9 / 230 = 3.9% |

> [!CAUTION]
> 96.1% of all tracks with sufficient observations are classified as cycling. This is conclusive evidence of systematic over-triggering.

---

## 2. Signal Ablation — Per-Signal Trigger Rates

Against all 230 tracks with ≥3 observations:

| Signal | Description | Tracks triggered | Rate |
|---|---|---:|---:|
| **Signal 1** | Bicycle proximity (dist < 0.25) | 205 | **89.1%** |
| **Signal 2 (speed only)** | mean_speed ≥ 0.018 | 227 | **98.7%** |
| **Signal 2 (height only)** | height_std < 0.03 | 124 | **53.9%** |
| **Signal 2 (both)** | speed ≥ 0.018 AND height_std < 0.03 | 121 | **52.6%** |

### Signal 1 fires for 89.1% of all tracks

This is caused by the mean-centroid proximity calculation without temporal alignment. The one confirmed bicycle track in archive_001 has a mean centroid that is within 0.25 normalized units of 89.1% of all tracked subjects — including subjects in indoor scenes, title cards, and other locations where the bicycle has never been.

### Signal 2 speed trigger fires for 98.7% of all tracks

The `CYCLE_HORIZ_THRESHOLD = 0.018 normalized/s` is below the speed of virtually every tracked object in this dataset. The minimum observed speed across all 230 tracks is **0.0119** — only 3 tracks (1.3%) have mean_speed below the cycling threshold.

```
CYCLE_HORIZ_THRESHOLD = 0.018
Observed minimum mean_speed = 0.0119 (1 track below threshold)
Tracks at or above 0.018: 227/230 = 98.7%
```

### Signal 2 height trigger fires for 53.9% of tracks

Height stability (height_std < 0.03) is satisfied by just over half of all tracks. These are predominantly distant/small detections with small bounding boxes that show minimal variance in normalized height.

### Combined Signal 2: 52.6% of tracks

The intersection of speed (98.7%) and height stability (53.9%) = 52.6% of all tracks are classified cycling by Signal 2 alone.

### Signal 1 + Signal 2 overlap: 221 total cycling

221 tracks are classified cycling. 205 trigger Signal 1, 121 trigger Signal 2 only (Signal 1 check returns first if triggered). 16 additional tracks are caught by Signal 2 that didn't trigger Signal 1.

---

## 3. Speed Distribution Analysis

### Full population (all 230 tracks with ≥3 obs)

| Percentile | mean_speed |
|---|---|
| Min | 0.01187 |
| P25 | 0.09143 |
| Median | 0.17023 |
| Mean | 0.18316 |
| P75 | 0.24991 |
| Max | 0.69114 |
| Std | 0.12871 |

**`CYCLE_HORIZ_THRESHOLD = 0.018` is at the 1.3th percentile of the speed distribution.** It is below all but 3 of the 230 tracks. This is not a discriminative threshold for cycling — it is a lower bound on motion that catches essentially every moving object.

### Speed of cycling vs non-cycling tracks

| Group | Count | Min | Median | Mean | Max |
|---|---|---|---|---|---|
| Cycling (n=221) | 221 | 0.01187 | 0.17121 | 0.18363 | 0.69114 |
| Non-cycling (n=9) | 9 | 0.01237 | 0.14619 | 0.17267 | 0.59274 |

The 9 non-cycling tracks do NOT have lower mean speeds than cycling tracks. They have comparable speeds (median 0.146 vs 0.171). The only reason they escaped cycling classification is that Signal 1 and Signal 2 both failed for them — either `height_std >= 0.03` AND they were outside Signal 1 radius.

---

## 4. Height Standard Deviation Distribution

### Full population

| Percentile | height_std |
|---|---|
| Min | 0.00155 |
| P25 | 0.00982 |
| Median | 0.02712 |
| Mean | 0.03841 |
| P75 | 0.05396 |
| Max | 0.23986 |
| Std | 0.03779 |

**The threshold `height_std < 0.03` sits at approximately the 50th percentile.** Half of all tracks naturally fall below this threshold — it is not a distinctive feature of seated/cycling posture in this footage.

At 320×240 resolution: a small detection box at 15px height has height = 15/240 = 0.0625 normalized. A ±1px height variation gives `height_std ≈ 0.004`. The `< 0.03` condition is trivially met by any detection box smaller than about 7.2 pixels standard deviation in height, which describes every distant/small person in the frame.

---

## 5. Audited Track Feature Values vs Distribution

The five tracks audited in Phase 6D.1 (all NOT_CYCLING):

| Track | Visual label | mean_speed | height_std | cycling_conf | Signal 1 | Signal 2 speed | Signal 2 height |
|---|---|---|---|---|---|---|---|
| 1 | Animated title silhouette | 0.0347 | 0.00587 | 0.65 | ✗ | ✓ | ✓ |
| 62 | Nurse arm movement (indoors) | 0.5076 | 0.08792 | 0.719 | ✓ | ✓ | ✗ |
| 234 | Man walking (outdoor) | 0.4021 | 0.02708 | 0.767 | ✓ | ✓ | ✓ |
| 285 | Pedestrians crossing (outdoor) | 0.2175 | 0.02070 | 0.782 | ✓ | ✓ | ✓ |
| 532 | Children near car (outdoor) | 0.0465 | 0.00608 | 0.729 | ✓ | ✓ | ✓ |

**Are the audited examples near the center of the distribution?**

- Track 1 (mean_speed=0.035): Near the bottom (3rd percentile of speed distribution). Yet still triggers Signal 2 — speed just above threshold.
- Track 62 (mean_speed=0.508): 97th percentile — extreme high speed. Triggers Signal 1 (bicycle proximity), not Signal 2 height (height_std=0.088 > 0.03).
- Track 234 (mean_speed=0.402): 90th percentile — high speed. Signal 1 triggers.
- Track 285 (mean_speed=0.218): 60th percentile — median region. Signal 1 triggers.
- Track 532 (mean_speed=0.046): 5th percentile — very low speed, yet Signal 2 triggers.

**The audited examples span the full distribution:** from the 3rd to 97th percentile of observed speeds. They were NOT chosen to be extreme outliers — they were distributed across the clip. This suggests false positives are distributed throughout the speed distribution, not concentrated in any specific range.

**Are the audited examples extreme outliers?**

NO. They span from near-minimum to near-maximum observed speeds. This confirms that the classifier is effectively a generic motion detector — it fires on objects of all speeds.

**Is there evidence the classifier is a generic motion detector?**

YES. `CYCLE_HORIZ_THRESHOLD = 0.018` catches 98.7% of all tracked objects. The threshold is not discriminative for cycling at this resolution.

---

## 6. Context Breakdown

S03 provides scene detection but does not tag individual frames as "indoor" / "outdoor" / "title card". No per-track scene label is available in the TCE context. Scene taxonomy from existing TCE data is unavailable at the required granularity.

**Only classification possible from available data:**

| Group | Count (estimate) | Basis |
|---|---|---|
| Tracks near bicycle (Signal 1) | 205 | Signal 1 firing |
| Signal 2 only (not near bicycle) | 16 | Signal 2 fires, Signal 1 does not |
| Neither signal | 9 | Not cycling |

Contextual breakdown (indoor/outdoor/title) is NOT available from TCE metadata. Frame-level scene context would require manual annotation or per-frame scene classification not present in this pipeline.

---

## 7. Frame-Skip / Resolution Analysis

### Speed threshold in pixel terms

| Resolution | CYCLE_HORIZ_THRESHOLD | px/s | px/observation (skip=5, fps=30) |
|---|---|---|---|
| 320×240 | 0.018 n/s | 5.76 px/s horizontal | **0.96 px** |
| 640×480 | 0.018 n/s | 11.52 px/s | 1.92 px |
| 848×480 (design) | 0.018 n/s | 15.26 px/s | 2.54 px |
| 1920×1080 (HD) | 0.018 n/s | 34.56 px/s | 5.76 px |

The normalized threshold formula divides by `dt` (frame timing), which makes the threshold appear resolution-independent. But the threshold value `0.018` was chosen with an implicit assumption about pixel density — at low resolution, even sub-pixel motion in original pixels can accumulate across 5 frames to exceed this threshold.

### Is the formula resolution-independent?

**NO.** The formula computes speed in `normalized_units / second`. This is resolution-independent for the centroid positions — a centroid at x=0.5 means "center of frame" regardless of pixel count. But the threshold `0.018` was empirically chosen at one resolution and is NOT automatically valid at another. At 320×240, the minimum detectable centroid shift (1 YOLO pixel) in normalized units is `1/320 = 0.003125`. Over 5 original frames, a person stationary in pixel space can still show a centroid shift of up to `5 × 0.003125 / 0.167 = 0.094 normalized/s` due to detection jitter. This is 5× the cycling threshold.

**Detection noise at 320×240 can independently trigger `mean_speed >= 0.018` without any real motion.**

---

## 8. Root Cause Conclusion

Two independent defects, both severe:

### Defect A: Signal 1 — No temporal alignment (PRIMARY for 89.1% of tracks)

The bicycle track in archive_001 (confirmed in S05) has a mean centroid that falls within 0.25 normalized of the mean centroid of 205/230 (89.1%) of all tracks. This cannot represent genuine co-location — the bicycle track does not occupy 89% of the frame. The cause is the mean-centroid comparison without temporal alignment: a bicycle appearing anywhere in the clip creates a proximity trigger for any person whose average position is within 0.25 normalized of the bicycle's average position.

### Defect B: Signal 2 — Threshold too low for 320×240 (PRIMARY for 98.7% of tracks)

`CYCLE_HORIZ_THRESHOLD = 0.018` catches 98.7% of all tracked objects at this resolution. The threshold was calibrated for higher-resolution indoor footage. At 320×240, detection jitter alone (sub-pixel bbox centroid noise amplified by the `/ dt` normalization) can approach this threshold. Any real motion exceeds it.

### Why they interact

Signal 1 fires first (returns immediately when triggered), so Signal 1 subsumes many tracks that would also trigger Signal 2. Of the 221 cycling tracks: ~205 are caught by Signal 1 (bicycle proximity defect), ~16 additional by Signal 2 alone. Both defects operate in parallel.

---

## 9. Candidate Fixes

### Fix A: Require temporal overlap for Signal 1 (addresses W4)

**Hypothesis:** The bicycle proximity check should only fire if person and bicycle tracks temporally co-exist in the same frame range.

**Evidence:** Track 62 (hospital, indoors) has Signal 1 firing (cycling_conf=0.719). The bicycle is in an outdoor scene. They share a similar mean centroid position purely by chance.

**Implementation:** In `_detect_cycling()`, before computing mean centroids, filter to the overlapping frame range between person and bicycle observations.

**Expected effect:** Eliminates false positives from Signal 1 where the person and bicycle appear in different scenes/time windows. Estimated 89.1% → near 0% Signal 1 trigger rate (no genuine cyclist confirmed in footage).

**Potential downside:** Requires frame-number-based overlap logic. Still does not address Signal 2.

**Validation experiment:** Re-run 300s with temporal overlap requirement. Verify cycling track count drops to ≤ confirmed bicycle appearances.

---

### Fix B: Raise Signal 2 speed threshold (resolution-adaptive) (addresses W1, W3)

**Hypothesis:** Replace `CYCLE_HORIZ_THRESHOLD = 0.018` with a higher value that separates cycling from walking at 320×240. At this resolution, cyclists move materially faster than pedestrians in normalized units.

**Evidence:** The speed distribution shows the minimum observed speed is 0.0119 and the threshold at 0.018 captures 98.7% of tracks. The walking threshold `WALK_THRESHOLD = 0.008` is BELOW `CYCLE_HORIZ_THRESHOLD = 0.018` — cycling should be detectably faster than walking, but both are above the current threshold. A reasonable cycling speed (18 km/h = 5 m/s) at 320px wide frame with 30fps: `5 / (real_scale_m_per_px × dt)` — requires knowing real-world scale.

Empirically: pedestrian walking speed at 320×240 occupies mean_speed ~0.10–0.25 normalized/s. Cyclists should be faster. A threshold around 0.3–0.5 normalized/s might separate genuine cyclists.

**Expected effect:** Reduces Signal 2 trigger rate dramatically. At threshold=0.30: only tracks with speed ≥ 0.30 trigger (approximately 25th–50th percentile range).

**Potential downside:** Requires re-calibration; may miss genuine slow cyclists. Also does not address Signal 1 defect.

**Validation experiment:** Apply threshold=0.30 (or similar) and rerun 300s. Check whether cycling count drops to near-zero. Watch 5 clips at new threshold.

---

### Fix C: Require horizontal dominance (addresses W1, W2)

**Hypothesis:** Cycling is dominantly horizontal motion. Add a condition that `mean_abs_vx / mean_speed > 0.7` (70% of motion is horizontal).

**Evidence:** `mean_abs_vx` is already computed in `classify()` (line 154) but not passed to `_detect_cycling()`. Nurse arm movement (Track 62, mean_speed=0.508) would have high vertical component; walking man (Track 234) would have high horizontal component but still not cycling. This alone may not be sufficient to eliminate all false positives.

**Expected effect:** Eliminates false positives from vertical motion (nurse arm, stair climbing). Does not eliminate horizontal pedestrian walking false positives.

**Potential downside:** Walking and cycling share horizontal motion direction. Does not discriminate well between walking and cycling alone.

**Validation experiment:** Compute `mean_abs_vx / mean_speed` for all cycling tracks. If nurse track (62) is eliminated but walking track (234) remains, this fix requires combination with Fix B.
