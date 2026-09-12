# Phase 6D.2 — Cycling Classifier Investigation

**Phase:** 6D.2  
**Baseline commit:** `bd9d18e` (Phase 6D.1 — cycling visual audit complete)  
**Date:** 2026-09-06 — 2026-09-13  
**Production code changed:** NO  
**Frozen config changed:** NO  
**595s validation:** NOT RUN

---

## 1. Objective

Phase 6D.1 confirmed all 5 sampled cycling-labelled tracks were NOT_CYCLING. Decision was `INVESTIGATE_CYCLING_CLASSIFIER_FIRST`.

This phase determines **exactly why** `ActivityClassifier` fires on non-cycling tracks, quantifies the scope of the over-trigger, characterises both signals, and proposes evidence-based candidate fixes.

No production code was modified. No thresholds were changed.

---

## 2. Baseline

| Item | Value |
|---|---|
| Baseline commit | `bd9d18e` |
| Dataset | archive_001, 300 seconds |
| Model | YOLO11l |
| Profile | balanced |
| frame_skip | 5 |
| detection_threshold | 0.25 |
| Video resolution | 320×240 |
| Video content | 1948 pedestrian safety film |
| Tests at baseline | 580 passing, 0 failures |

---

## 3. Current Classifier Logic

Source: [`activity_classifier.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/utils/activity_classifier.py) — see full audit: [`phase-6d-2-cycling-classifier-audit.md`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/reports/phase-6d-2-cycling-classifier-audit.md)

### Decision tree position

Cycling is evaluated FIRST in the decision tree (line 189). A `cycling_conf ≥ 0.60` result immediately returns without evaluating walking, running, or loitering. There is no override path.

### Signal 1: Bicycle Track Proximity

```python
dist = sqrt((mean(person_cx) - mean(bike_cx))^2 + (mean(person_cy) - mean(bike_cy))^2)
if dist < 0.25:
    return max(0.70, 0.95 - dist * 2)
```

Fires when a confirmed bicycle track's mean centroid is within 0.25 normalized of the person track's mean centroid. No temporal alignment — mean centroids over the entire clip are compared.

### Signal 2: Speed + Height Stability

```python
if mean_speed >= 0.018:                # CYCLE_HORIZ_THRESHOLD
    height_std = std([o.bbox.height])
    if height_std < 0.03:
        return 0.65
```

Fires when `mean_speed` (2D total vector speed, normalized/s) ≥ 0.018 AND bounding-box height standard deviation < 0.03 normalized.

**Key: `mean_speed` is the 2D magnitude, not horizontal speed alone.**

---

## 4. Dataset and Artifacts

| Artifact | Location |
|---|---|
| Feature extraction data | `results/TCE-v1.0/phase6d2-cycling-track-features.json` |
| Extraction script | `backend/scripts/phase6d2_extract_cycling_features.py` |
| Classifier audit | `reports/phase-6d-2-cycling-classifier-audit.md` |
| Signal analysis | `reports/phase-6d-2-cycling-signal-analysis.md` |
| Visual audit | `reports/cycling-visual-audit-archive001-300s.md` |

Method: S01–S05 of the standard pipeline was replayed on archive_001 300s with the frozen Phase 6B/6D configuration. Track objects with ≥3 observations (minimum required to reach Signal 2) were extracted and the exact same features ActivityClassifier computes were recalculated for each track, with individual signal ablation.

---

## 5. Signal Analysis — Numbers

### Population

| Metric | Value |
|---|---|
| Total tracks (all classes) | 546 |
| Tracks with ≥3 observations | 230 |
| Classified as cycling | **221 (96.1%)** |
| Not classified as cycling | 9 (3.9%) |

### Per-signal ablation (against 230 tracks)

| Signal | Trigger rate |
|---|---|
| Signal 1 (bicycle proximity) | **89.1% (205/230)** |
| Signal 2: speed ≥ 0.018 | **98.7% (227/230)** |
| Signal 2: height_std < 0.03 | 53.9% (124/230) |
| Signal 2: both conditions | 52.6% (121/230) |

### Speed distribution (all 230 tracks)

| | min | P25 | median | mean | P75 | max |
|---|---|---|---|---|---|---|
| mean_speed | 0.012 | 0.091 | 0.170 | 0.183 | 0.250 | 0.691 |

`CYCLE_HORIZ_THRESHOLD = 0.018` sits at the **1.3th percentile** of observed speeds. 227/230 tracks (98.7%) exceed it.

### Height_std distribution (all 230 tracks)

| | min | P25 | median | mean | P75 | max |
|---|---|---|---|---|---|---|
| height_std | 0.002 | 0.010 | 0.027 | 0.038 | 0.054 | 0.240 |

`height_std < 0.03` threshold falls at approximately the **50th percentile**. Half of all tracks naturally fall below it.

### Cycling vs non-cycling speed comparison

The 9 non-cycling tracks have comparable speeds to the 221 cycling tracks:
- Cycling median speed: 0.169
- Non-cycling median speed: 0.181

Non-cycling tracks were not slower — they simply had `height_std ≥ 0.03` and fell outside Signal 1 radius. There is no speed-based separation between the two groups.

---

## 6. Frame-Skip / Resolution Dependency

The threshold `CYCLE_HORIZ_THRESHOLD = 0.018 normalized/s` is expressed in resolution-independent normalized units. However, the value itself was calibrated for higher-resolution indoor CCTV footage. At 320×240:

```
1 pixel of centroid shift  = 1/320 = 0.003125 normalized (horizontal)
dt per observation         = 5/30 = 0.167 seconds
Detection jitter (1px)     = 0.003125 / 0.167 = 0.019 normalized/s
```

**Detection jitter from a single pixel of centroid noise is 0.019 normalized/s — which is above the 0.018 threshold.** Any track that experiences even one-pixel YOLO detection noise between consecutive frames satisfies the speed threshold, with no real motion required.

This is not a coincidence: the minimum observed mean_speed (0.0119) is already only marginally below 0.018. A single additional pixel of noise would push it over.

The formula is NOT resolution-independent in practice because the threshold encodes an assumption about what pixel displacement counts as "cycling speed."

---

## 7. Visual Audit Relationship

Phase 6D.1 inspected 5 tracks distributed across the speed distribution (3rd to 97th percentile). All 5 were NOT_CYCLING. This investigation confirms they are not outliers:

| Track | Speed percentile | Signal 1 | Signal 2 | Visual |
|---|---|---|---|---|
| 1 | ~3rd | ✗ | ✓ | Animated title card |
| 532 | ~5th | ✓ | ✓ | Children near car |
| 285 | ~60th | ✓ | ✓ | Pedestrians crossing |
| 234 | ~90th | ✓ | ✓ | Man walking |
| 62 | ~97th | ✓ | ✗ | Nurse arm movement |

The 5 audited tracks span the full speed distribution and represent multiple scene types. The false positive mechanism differs across them:

- Tracks at low speed (1, 532): Signal 2 triggers, sometimes combined with Signal 1
- Tracks at mid/high speed (285, 234, 62): Signal 1 triggers (bicycle proximity, no temporal alignment)
- One high-speed indoor track (62): Only Signal 1 triggers (height_std = 0.088 > 0.03, so Signal 2 height fails)

The diversity of false-positive causes across the distribution suggests the audited sample is representative of the broader cycling population structure.

---

## 8. Root Cause Conclusion

### Root Cause A: Signal 1 — Mean centroid proximity without temporal alignment

**Mechanism:** The one confirmed bicycle track in archive_001 has a mean centroid over 300 seconds that falls within 0.25 normalized of 89.1% of all person tracks' mean centroids. This is geometrically possible because mean centroids over the entire clip duration converge toward the frame center for tracks that appear from different edges or move across the frame.

**Evidence:** Track 62 (hospital scene, indoors) has Signal 1 cycling_conf = 0.719 from bicycle proximity. The bicycle never appears indoors. This is only possible without temporal alignment.

**Consequence:** Signal 1 is effectively a constant classifier for this footage — it fires for nearly any track whose mean position is in the central 50% of the frame, regardless of what the person is doing or when they appear.

### Root Cause B: Signal 2 — `CYCLE_HORIZ_THRESHOLD = 0.018` at sub-pixel level

**Mechanism:** At 320×240 with frame_skip=5, the threshold equals approximately 1 pixel per observation. YOLO detection noise alone (~0.5–2px centroid jitter) can produce `mean_speed ≥ 0.018` with no real motion. Any actual movement exceeds the threshold unconditionally.

**Evidence:** 98.7% of all tracks (227/230) exceed the threshold. The minimum observed speed (0.0119) is just 33% below the threshold. Three tracks are below threshold only because they have near-zero real motion AND below-average detection noise.

**Consequence:** Signal 2 speed condition is a motion-presence detector, not a cycling detector. The height stability condition partially gates it (53.9% pass) but is itself non-discriminative for cycling vs walking at this resolution.

### Combined effect

Signal 1 fires for 89.1% of tracks regardless of scene. Signal 2 fires for an additional 52.6% (mostly subset, with 16 exclusive to Signal 2). Together 96.1% of all tracks are classified cycling. The classifier is not detecting cycling — it is detecting track existence.

---

## 9. Candidate Fixes

### Candidate A — Fix Signal 1: Require Temporal Overlap

**Hypothesis:** Bicycle proximity should only count if person and bicycle tracks share overlapping frame ranges — i.e., they exist in the video at the same time.

**Evidence supporting:** Track 62 (indoors, hospital) triggers Signal 1 from a bicycle in an outdoor scene. The temporal overlap check would eliminate this by confirming the two tracks never share a frame.

**Expected effect:** Reduces Signal 1 trigger rate from 89.1% toward the true co-location rate (likely < 5% for this footage). Eliminates cross-scene false positives.

**Implementation:** In `_detect_cycling()`, compute overlap between `[obs[0].frame_number, obs[-1].frame_number]` for person and bicycle tracks. Only compare centroids if overlap exists.

**Potential downside:** Does not address Signal 2. After fixing Signal 1, Signal 2 alone would still fire for ~52.6% of tracks.

**Validation experiment:** Apply temporal overlap filter; rerun 300s; measure cycling track count reduction; watch 3 remaining cycling clips to confirm they are genuine.

---

### Candidate B — Raise Signal 2 Speed Threshold (Resolution-Aware)

**Hypothesis:** Replace the fixed `0.018` threshold with a higher value that sits above the observed walking/standing speed distribution but below genuine cycling speed.

**Evidence supporting:** Pedestrian median speed = 0.170 normalized/s. A genuine cyclist at 15 km/h in this footage would move at approximately 0.3–0.5 normalized/s based on expected pixel velocities at 320×240. A threshold of `0.15–0.20` would place the cutoff at the lower walking range; `0.30+` would be above typical pedestrian speeds.

**Limitation:** This footage contains no confirmed cyclists to establish a ground-truth cycling speed floor. Any new threshold is a hypothesis, not a calibrated value.

**Expected effect:** At threshold = 0.30, only 25% of tracks (P75 = 0.250) trigger Signal 2. Combined with Signal 1 fix, total cycling rate could drop to a realistic 5–15%.

**Potential downside:** Slow cyclists or distant cyclists may have lower normalized speeds. Raising the threshold risks missing genuine cyclists in future footage.

**Validation experiment:** Compute speed for a known cycling clip (e.g., archive_002 if it contains cyclists). Set threshold at 2× the pedestrian median (0.34). Rerun 300s and rerun visual audit on remaining cycling tracks.

---

### Candidate C — Require Horizontal Dominance for Signal 2

**Hypothesis:** Genuine cycling is predominantly horizontal motion. Add condition: `mean_abs_vx / mean_speed > 0.70` (70% of motion must be horizontal).

**Evidence supporting:** `mean_abs_vx` is already computed in `classify()` (line 154). Track 62 (nurse, arm swinging) would likely fail this test (vertical arm swing). Track 1 (animated title, horizontal motion) might still pass.

**Expected effect:** Eliminates false positives from vertical motion (arm swings, stair climbing). Does not eliminate horizontal pedestrian walking false positives.

**Potential downside:** A cyclist riding toward the camera (purely vertical motion in frame) would fail this check. Walking is also predominantly horizontal, so this alone does not separate walking from cycling.

**Note:** `mean_abs_vx` is available as a feature but is NOT currently passed to `_detect_cycling()`. Implementation would require adding it as a parameter.

**Validation experiment:** Compute `mean_abs_vx / mean_speed` for all 221 cycling tracks from Phase 6D.2 data. Determine what fraction fails the 0.70 threshold. Predict effect before implementing.

---

## 10. Recommended Next Experiment — Phase 6D.3

**Title:** Fix Signal 1 temporal alignment + raise Signal 2 threshold; validate on 300s

**Scope:**
1. Add temporal overlap filter to Signal 1: person and bicycle tracks must overlap in frame range to count as proximate.
2. Raise `CYCLE_HORIZ_THRESHOLD` from `0.018` to a threshold derived from the measured pedestrian speed distribution (e.g., 0.25 normalized/s — the 75th percentile of the current speed distribution, which is above most pedestrian walking but within range of fast movers).
3. Regression-test on 300s: verify cycling track count drops dramatically.
4. Visual audit: watch 5 new cycling clips post-fix to confirm classifications improve.
5. Do NOT proceed to 595s until visual audit passes.

**Justification:** Both root causes are independent and both need fixing. A partial fix (Signal 1 only) still leaves 52.6% cycling from Signal 2. A partial fix (Signal 2 threshold raise only) still leaves 89.1% cycling from Signal 1 temporal misalignment.

**What would constitute success:**
- Cycling track count drops from 221/230 (96.1%) to < 20/230 (< 8%)
- Visual audit of 5 new cycling clips shows ≥ 3/5 GENUINE_CYCLING or AMBIGUOUS
- No regression in existing tests

---

## 11. Limitations

1. **No ground-truth cyclist labels** for archive_001. It is not possible to state the true-positive rate or compute precision/recall.
2. **5 visual samples** from Phase 6D.1 are not a precision measurement. They demonstrate systematic over-trigger across the speed distribution but do not quantify exact false-positive rate.
3. **Single bicycle track** confirmed in S05 for archive_001. Footage from Phase 6B confirms 1 bicycle track. All Signal 1 triggers are attributable to this one track. A different dataset with more bicycle tracks could behave differently.
4. **Feature extraction replay** (S01–S05) produces slightly different track IDs across runs due to non-deterministic YOLO inference. Track IDs between Phase 6B (229 person tracks) and Phase 6D.2 (249 person tracks) differ. Feature analysis uses Phase 6D.2 extraction, which is the most recent and reproducible.
5. **Mean centroid Signal 1 geometry** was not exhaustively modelled — the 89.1% figure is measured, not analytically explained. It depends on this specific footage and clip length.

---

## 12. Explicit Statement

No production source code was modified in Phase 6D.2.  
No configuration files were modified.  
No thresholds were changed.  
The frozen TCE_V1_REFERENCE configuration is unchanged.  
The experiment commit contains only: reports, diagnostic data, diagnostic scripts, and diagnostic tests.
