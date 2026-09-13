# Phase 6E.1 — Failure Trace Report

**Phase:** 6E.1  
**Baseline commit:** `c1351c6`  
**Date:** 2026-09-13  

---

## 0. Measured Inputs

All measurements were obtained by running `phase6e1_camera_motion_audit.py` — a diagnostic-only script that replicates the S01–S06 pipeline on the 300s archive_001 clip and re-runs ActivityClassifier with Phase 6D.4 experimental settings (`cycle_threshold=0.25`, `require_temporal_overlap=True`).

Pipeline settings used: `frame_skip_rate=5`, `fps=29.97`  
`_dt` in ActivityClassifier: `5 / 29.97 = 0.1668s` per extracted frame

**Thresholds in effect (from activity_classifier.py):**

| Constant | Value | Meaning |
|---|---|---|
| `STILL_THRESHOLD` | 0.003 | cx/cy change/frame below = stationary |
| `WALK_THRESHOLD` | 0.008 | moderate walking pace |
| `RUN_THRESHOLD` | 0.022 | running (high velocity) |
| `STAIR_VERT_THRESHOLD` | 0.005 | sustained vertical velocity = stairs |

**Camera motion frames:** 53 total (frames 22–1784).

---

## 1. Track 56 — predicted: `running`

**Measured quantities:**

| Field | Value |
|---|---|
| `obs_count` | 43 |
| `frame_range` | 263–360 |
| `start_ms` | 43,877 |
| `end_ms` | 60,060 |
| `mean_speed` | **0.37821** |
| `RUN_THRESHOLD` | 0.022 |
| `mean_vy` | -0.02260 |
| `n_vy_up` | 19 / 42 = 45.2% |
| `n_vy_down` | 16 / 42 = 38.1% |
| `cam_overlap_frames` | 0 / 43 = **0.0%** |
| `would_be_suppressed_pass1` | False |
| `activity_label` | running |
| `activity_confidence` | 0.950 |

**Decision tree path:**

- `cycling_conf < 0.60` — skip cycling
- `stair_conf < 0.55` — `n_vy_up/n_total=45%` (< 50%) → stair_conf = 0.0 — skip stairs
- `mean_speed=0.378 >= RUN_THRESHOLD=0.022` → **FIRES: running**
- Confidence: `min(0.95, 0.70 + (0.378 - 0.022) × 10) = min(0.95, 4.26) = 0.95`

**Why fired:** The running threshold `RUN_THRESHOLD=0.022` is expressed in normalized-frame-units per extracted-frame. `mean_speed=0.378` is 17× the threshold. This is an extremely high speed signal.

**Visual reality (Phase 6D.5):** Indoor hospital room. Doctor (in white coat, stethoscope) leaning over a patient in bed. Nurse standing in background. The person track covers the doctor's torso across ~16s of footage during a close-up camera sequence.

**Diagnosis:** In a hospital close-up shot, the camera moves in (zoom or dolly), and the tracked person occupies a larger portion of the frame. As the doctor leans forward and the camera zooms in, the bbox centroid shifts rapidly within the frame — producing a high `mean_speed` despite no locomotion. This is **camera zoom / close-up tracking artifact**: the centroid displacement reflects camera motion (not detected as camera motion because it is smooth zoom, not pan, and may only affect one track rather than all tracks simultaneously).

**Root cause: SCENE_GEOMETRY (camera zoom artifact), secondary: DETECTION_JITTER**

---

## 2. Track 160 — predicted: `running`

**Measured quantities:**

| Field | Value |
|---|---|
| `obs_count` | 45 |
| `frame_range` | 814–888 |
| `start_ms` | 135,802 |
| `end_ms` | 148,148 |
| `mean_speed` | **0.13795** |
| `RUN_THRESHOLD` | 0.022 |
| `mean_vy` | -0.01533 |
| `n_vy_up` | 17 / 44 = 38.6% |
| `n_vy_down` | 14 / 44 = 31.8% |
| `cam_overlap_frames` | 6 / 45 = **13.3%** |
| `cam_overlap_frame_numbers` | 821, 836, 843, 876, 878, 882 |
| `would_be_suppressed_pass1` | False |
| `activity_label` | running |
| `activity_confidence` | 0.950 |

**Decision tree path:**

- `cycling_conf < 0.60` — skip cycling
- `stair_conf < 0.55` — `n_vy_up/n_total=38.6%` (< 50%) → stair_conf = 0.0 — skip stairs
- `mean_speed=0.138 >= RUN_THRESHOLD=0.022` → **FIRES: running**
- Confidence: `min(0.95, 0.70 + (0.138 - 0.022) × 10) = min(0.95, 1.86) = 0.95`

**Why fired:** `mean_speed=0.138` is 6.3× the running threshold. Stair detection did not fire (only 38.6% of frames have upward vy — insufficient for 50% dominance threshold).

**Visual reality (Phase 6D.5):** Frame 814 (02:16): Traffic officer standing at intersection directing traffic. Frames 843–888 (02:21–02:27): Overhead/bird's-eye camera angle of a sidewalk — pedestrian silhouettes viewed from directly above.

**Diagnosis:** The overhead camera angle means the video undergoes a **scene cut** mid-track: ground-level footage cuts to aerial overhead footage. During this transition the tracked "person" may be a different detection, or the same track acquires very different kinematics from the overhead angle. At overhead angles, a person walking normally produces rapid centroid drift because the pixel-coordinates of their centroid change rapidly as they walk under the camera. `mean_speed=0.138` is plausibly a real pedestrian walking at a normal pace when viewed directly from overhead (high pixel-to-real-distance ratio).

**Camera overlap:** 6 frames (13.3%) are in camera-motion frames. However 38/45 (86.7%) are not. The track would NOT be suppressed by Pass 1's `issubset` guard.

**Root cause: SCENE_GEOMETRY (overhead camera angle producing inflated centroid velocity), secondary: DETECTION_JITTER (scene cut)**

---

## 3. Track 366 — predicted: `running`

**Measured quantities:**

| Field | Value |
|---|---|
| `obs_count` | **3** |
| `frame_range` | 1475–1478 |
| `start_ms` | 246,079 |
| `end_ms` | 246,580 |
| `mean_speed` | **0.12742** |
| `RUN_THRESHOLD` | 0.022 |
| `mean_vy` | **-0.11239** |
| `n_vy_up` | 2 / 2 = **100%** |
| `n_vy_down` | 0 / 2 = 0% |
| `cam_overlap_frames` | 0 / 3 = **0.0%** |
| `would_be_suppressed_pass1` | False |
| `activity_label` | running |
| `activity_confidence` | 0.950 |

**Decision tree path:**

- `len(obs) < 3` check: fails at line 147 — `len(obs) = 3`, and the condition is `< 3`, so it proceeds (3 is NOT < 3)
- `cycling_conf < 0.60` — skip cycling
- `stair_conf`: `len(vy_arr) = 2 < 4` → early return `(0.0, "up")` — skip stairs
- `mean_speed=0.127 >= RUN_THRESHOLD=0.022` → **FIRES: running**
- Confidence: `min(0.95, 0.70 + (0.127 - 0.022) × 10) = min(0.95, 1.75) = 0.95`

**Note on stair guard:** `_detect_stairs` requires `len(vy_arr) >= 4`. With 3 observations, `len(vy_arr) = 2`, so stair detection is disabled. But even if stair detection ran, `n_vy_up=2/2=100%` with `mean_vy=-0.112` (= 22× `STAIR_VERT_THRESHOLD`) would have fired stair detection first. Running fired because stair detection was disabled for short tracks.

**Note on obs count guard:** The `len(obs) < 3` guard at line 147 uses strict less-than. A track with exactly 3 observations passes this guard and proceeds to full classification. A track with 1 or 2 observations returns `"entering_scene"`.

**Visual reality (Phase 6D.5):** Overhead/bird's-eye view of intersection. A small pedestrian visible at top-right walking on sidewalk. Only 3 frames of existence (0.5 seconds). Cannot determine actual gait from visual evidence — track too brief.

**Diagnosis:** Pure **SHORT_TRACK instability**. With 3 observations (2 velocity measurements), the classifier has minimal data. A single noisy observation pair produces `mean_speed=0.127` (6× running threshold). The `vy=-0.112` per-frame is enormous — 22× the stair threshold — indicating this is measurement noise or a rapid camera cut rather than actual vertical locomotion.

**Root cause: SHORT_TRACK (3 observations insufficient for reliable classification), secondary: DETECTION_JITTER**

---

## 4. Track 14 — predicted: `walking_upstairs`

**Measured quantities:**

| Field | Value |
|---|---|
| `obs_count` | 28 |
| `frame_range` | 183–232 |
| `start_ms` | 30,531 |
| `end_ms` | 38,705 |
| `mean_speed` | **0.39485** |
| `WALK_THRESHOLD` | 0.008 |
| `mean_vy` | -0.02266 |
| `STAIR_VERT_THRESHOLD` | 0.005 |
| `n_vy_up` | 15 / 27 = **55.6%** |
| `n_vy_down` | 12 / 27 = 44.4% |
| `cam_overlap_frames` | 3 / 28 = **10.7%** |
| `cam_overlap_frame_numbers` | 189, 217, 232 |
| `would_be_suppressed_pass1` | False |
| `activity_label` | walking_upstairs |
| `activity_confidence` | 0.733 |

**Stair detection calculation:**

```
dominant_frac = 15/27 = 0.556  (n_up > n_down)
direction = "up"

dominant_frac >= 0.50  → continues

mean_vy_abs = mean(|vy_arr|)  # measured ~0.023 (mean_vy is signed mean)
magnitude_factor = min(1.0, 0.023 / (0.005 * 3)) = min(1.0, 1.53) = 1.0

confidence = 0.556 * 0.6 + 1.0 * 0.4 = 0.334 + 0.4 = 0.734

mean_speed = 0.395 >= WALK_THRESHOLD * 0.5 = 0.004  → no penalty

stair_conf = min(0.93, 0.734) = 0.733
stair_conf >= 0.55  AND  mean_speed >= WALK_THRESHOLD → FIRES walking_upstairs
```

**Why fired:** 55.6% of frame pairs have upward vertical velocity (just above the 50% threshold). Combined with high speed (0.395 >> WALK_THRESHOLD), the stair classifier fires with confidence 0.733.

**Visual reality (Phase 6D.5):** Outdoor scene. Two police officers at the rear of an ambulance vehicle. They appear to be loading something or handling the ambulance rear door. The scene is filmed at normal camera height.

**Diagnosis:** The ambulance scene is filmed from a slight upward angle on the subjects, and the action of loading the ambulance involves the officer bending forward and moving toward the back of the vehicle. As the officer moves toward the ambulance rear (moving away from camera = centroid moves up in image), the vy_up signal fires. The centroid motion is entirely **body motion in 3D space** — specifically moving away from camera rather than climbing stairs. This is a **BODY_MOTION_CONFUSION** failure: the stair signal does not distinguish "centroid moving up in image" from "person walking upstairs."

**Camera overlap:** 3 frames (10.7%) — slight partial overlap. NOT sufficient for Pass 1 suppression (issubset would require all 28 frames to be in camera_motion_frames).

**Root cause: BODY_MOTION_CONFUSION (horizontal motion toward camera creates upward vy signal), secondary: SCENE_GEOMETRY**

---

## 5. Track 177 — predicted: `walking_upstairs`

**Measured quantities:**

| Field | Value |
|---|---|
| `obs_count` | 27 |
| `frame_range` | 843–909 |
| `start_ms` | 140,641 |
| `end_ms` | 151,652 |
| `mean_speed` | **0.16826** |
| `WALK_THRESHOLD` | 0.008 |
| `mean_vy` | -0.01777 |
| `STAIR_VERT_THRESHOLD` | 0.005 |
| `n_vy_up` | 15 / 26 = **57.7%** |
| `n_vy_down` | 9 / 26 = 34.6% |
| `cam_overlap_frames` | 6 / 27 = **22.2%** |
| `cam_overlap_frame_numbers` | 843, 876, 878, 898, 905, 908 |
| `would_be_suppressed_pass1` | False |
| `activity_label` | walking_upstairs |
| `activity_confidence` | 0.746 |

**Stair detection calculation:**

```
dominant_frac = 15/26 = 0.577  (n_up > n_down)
direction = "up"

dominant_frac >= 0.50  → continues

mean_vy_abs ≈ 0.018 (estimated from mean_vy = -0.0178, predominantly negative)
magnitude_factor = min(1.0, 0.018 / (0.005 * 3)) = min(1.0, 1.2) = 1.0

confidence = 0.577 * 0.6 + 1.0 * 0.4 = 0.346 + 0.4 = 0.746
stair_conf = min(0.93, 0.746) = 0.746
stair_conf >= 0.55  AND  mean_speed >= WALK_THRESHOLD → FIRES walking_upstairs
```

**Visual reality (Phase 6D.5):** Same overhead/bird's-eye scene as Track 160 — sidewalk viewed from directly above. Pedestrian silhouettes walking on level ground.

**Diagnosis:** Track 177 is in the same overhead-angle scene as Track 160 at an overlapping time window (frames 843–909 vs 814–888 for Track 160). This is a **SCENE_GEOMETRY** failure. When a camera is mounted directly overhead and a person walks forward (horizontally on the ground), their centroid moves toward the top of the frame (vy decreasing = upward = stair signal). The stair classifier is designed for fixed-angle CCTV cameras, not overhead cameras. With 57.7% of frames showing upward vertical velocity, the stair condition fires despite no stairs being present.

**Camera overlap:** 6 frames (22.2%) — the highest of any audit track. Still not sufficient for Pass 1 suppression.

**Root cause: SCENE_GEOMETRY (overhead camera angle maps ground-level walking to upward vy), secondary: CAMERA_MOTION (6/27 frames partial overlap)**

---

## 6. Camera Motion Overlap Summary

| Track | Predicted action | Camera-motion frames | Track frames | Overlap % | Suppressed by Pass 1? |
|---|---|---|---|---|---|
| 56  | running          | 0 | 43 | 0.0%  | No |
| 160 | running          | 6 | 45 | 13.3% | No |
| 366 | running          | 0 | 3  | 0.0%  | No |
| 14  | walking_upstairs | 3 | 28 | 10.7% | No |
| 177 | walking_upstairs | 6 | 27 | 22.2% | No |

**Conclusion: Camera motion is NOT the primary cause of any of the 5 failures.**

The 53 camera-motion-flagged frames are concentrated in frames 20–145 (the first ~5 seconds of video, which contains the animated title card) and scattered frames 821–1784. None of the audit tracks exist entirely within camera-motion frames. Pass 1's suppression (which requires `issubset`) would not have suppressed any of these tracks even if it were applied to Pass 7.

---

## 7. Root Cause Classification

| Track | Primary root cause | Secondary root cause | Evidence |
|---|---|---|---|
| 56  | SCENE_GEOMETRY (camera zoom / close-up artifact) | DETECTION_JITTER | mean_speed=0.378 from indoor close-up; 0 camera-motion overlap |
| 160 | SCENE_GEOMETRY (overhead camera angle) | DETECTION_JITTER (scene cut) | mean_speed=0.138 from overhead shot; running threshold exceeded by 6× |
| 366 | SHORT_TRACK (3 obs, 0.5s) | DETECTION_JITTER | obs=3; stair detector disabled (requires ≥4 obs); vy=-0.112 (noise) |
| 14  | BODY_MOTION_CONFUSION (approach motion = upward vy) | SCENE_GEOMETRY | n_vy_up=55.6%, mean_speed=0.395; ambulance loading scene |
| 177 | SCENE_GEOMETRY (overhead camera = upward vy on ground) | CAMERA_MOTION (22.2% partial overlap) | n_vy_up=57.7%; same overhead scene as Track 160 |

---

## 8. Positive Activity Ground Truth (Step 8)

**Systematic check for genuine running, walking upstairs, walking downstairs in archive_001 (300s clip):**

The footage is a 1948 pedestrian safety film with the following confirmed scene types:
- Animated title card (0–13s)
- Outdoor ambulance scene (30–45s)
- Hospital interior close-ups (44s–1:30s)
- Outdoor intersection / overhead shots (2:00s–3:00s)
- Suburban street scenes (3:00s–4:00s)
- Outdoor pathways (4:00s–5:00s)

**Running:** The animated title card (Track 1) shows stylized running silhouettes in a 2D graphic. No genuine person is observed running in any inspected frame. The tracking system produces 4 "running" labels — all false positives (Tracks 56, 160, 366, and one additional). The film does not appear to include any footage of a person running.

**Walking upstairs:** No staircase is visible in any inspected frame. The 4 "walking_upstairs" labels all arise from vy artifacts. No positive ground truth observed.

**Walking downstairs:** Not classified in any of the 10 complete stories. Not observed in inspected frames.

**Positive ground truth status:**

> **No positive ground truth available in archive_001 for running, walking_upstairs, or walking_downstairs.**
>
> This means: we cannot validate whether the activity classifiers can correctly detect these actions. We can only measure false positive rate on this footage. The false positive rate for running and walking_upstairs from this audit is 5/5 = 100% — but this is a property of archive_001 footage, not of the classifier's general capability.

---

## 9. Existing Guard — Evaluation for Pass 7 Reuse

**Question:** Would reusing the Pass 1 camera-motion guard in Pass 7 suppress the 5 failures?

**Answer: NO.** The guard uses `track_frames.issubset(camera_frames)`. None of the 5 tracks is entirely within camera-motion frames (overlaps range from 0% to 22.2%). Even with a partial-overlap variant (e.g., "suppress if >50% frames in camera-motion"), it would not affect Tracks 56, 366 (0% overlap) and only marginally affect Tracks 14, 160, 177.

**Would it suppress genuine running/upstairs?** Potentially yes. If the video contains a person running during a camera pan, the camera-motion guard might suppress a genuine running event. Without positive ground truth, this risk cannot be quantified.

**Semantically safe?** Only if we use the same logic as Pass 1: suppress when ALL frames are in camera-motion. Partial suppression creates non-deterministic behavior depending on what fraction of a person's track happens to coincide with camera motion.

**Conclusion:** The camera-motion guard is not the right fix for these failures. The failures require separate fixes for each root cause category.

---

## 10. Candidate Fixes

### Candidate A — Minimum Observation Count Guard

**Description:** Suppress narrative_builder activity events for tracks with fewer than N observations (e.g., N=10).

**Targets:** SHORT_TRACK (Track 366).

**Expected FP reduction:** Eliminates Track 366 class of failures. At N=10: eliminates all tracks with < 10 observations from receiving activity labels. Track 366 (obs=3) would be suppressed.

**Risk of false negatives:** Any genuine action lasting < `N × frame_skip / fps` seconds would be suppressed. At N=10, frame_skip=5, fps=30: minimum detectable action = 10 × 5/30 = 1.67 seconds. This is a reasonable minimum for any genuine running or stair-climbing event.

**Implementation complexity:** Low. Single integer check added to Pass 7 before emitting narrative events.

**Evidence:** Track 366 has obs=3. ActivityClassifier already handles obs<3 as `entering_scene`. The gap is obs=3 specifically (passes the `< 3` guard but is insufficient for reliable classification).

**Experiment needed:** Add guard, re-run 300s, verify Track 366 suppressed and no other audit tracks affected.

---

### Candidate B — Scene Geometry / Overhead Camera Normalization (vy correction)

**Description:** Detect when the camera is at a near-overhead angle by computing the mean `vy` across all active tracks in a time window. If the mean population `vy` (across all tracks) is significantly negative (upward drift), normalize individual track `vy` by subtracting this population mean before applying stair detection.

**Targets:** SCENE_GEOMETRY for stair detection (Tracks 14, 177). Possibly also Track 160 for running.

**Expected FP reduction:** Eliminates overhead-angle stair false positives. In overhead shots, all tracks will show negative vy (upward drift toward camera). Subtracting population mean vy from each track's individual vy would remove the shared component, leaving only the relative upward motion (which would be near-zero for level walking).

**Risk of false negatives:** If a genuine stair scene has most people going up at once (e.g., a staircase scene), the correction would suppress those events. However, genuine stairs in CCTV footage are typically not shot from directly overhead.

**Implementation complexity:** Medium. Requires propagating population vy statistics from S06 MotionAnalyzer into ActivityClassifier, or computing them in S05. The vy population statistics are not currently computed in S06.

**Evidence:** Tracks 160 and 177 are in the same overhead scene. Track 14 shows a different failure (ambulance loading → approach motion) that may not be corrected by this approach.

**Experiment needed:** Compute population-mean vy per time window in S06; pass to ActivityClassifier; validate that stair detection is suppressed for Tracks 177/160 and not suppressed for any genuine stair case (no positive ground truth available for validation — this is a risk).

---

### Candidate C — Speed Threshold Adjustment for `running`

**Description:** Raise `RUN_THRESHOLD` to reduce false positive rate for the running label. Current threshold 0.022. Track 160 fires at 0.138 (6×), Track 56 fires at 0.378 (17×), Track 366 at 0.127 (6×).

**Targets:** SCENE_GEOMETRY for running (Tracks 56, 160). Note: Tracks 56 and 160 would STILL fire even at `RUN_THRESHOLD=0.10` (Track 56: 3.8×; Track 160: 1.38×). Only Track 366 might be suppressed by a higher threshold.

**Expected FP reduction:** Limited. Track 366 (speed=0.127) would be suppressed at `RUN_THRESHOLD >= 0.130`. Track 160 (speed=0.138) would be suppressed at `RUN_THRESHOLD >= 0.139`. Track 56 (speed=0.378) would require `RUN_THRESHOLD >= 0.379` — this would be so high that genuine running would likely be missed.

**Risk of false negatives:** Raising the threshold beyond 0.05–0.10 would likely suppress genuine running. Without positive ground truth, this cannot be safely calibrated.

**Implementation complexity:** Low. Single constant change.

**Evidence:** Does not address the root cause (scene geometry, short tracks) — only masks symptoms. A person running in an overhead shot would still exceed any reasonable running threshold.

**Verdict:** NOT recommended as a primary fix. At most a secondary adjustment after Candidate A or B are validated.

---

## 11. Recommendation

**Primary fix for Phase 6E.2:**

1. **Candidate A** (minimum obs count guard, N ≥ 10 or N ≥ 5 with evidence): Simple, low-risk, directly addresses Track 366 class. Implement as a threshold parameter in narrative_builder (not a hardcoded constant). Default=5 (above existing `< 3` guard, below 10).

2. **Candidate B** (population vy normalization): Addresses Tracks 14, 177, 160. Higher complexity — requires extending S06 MotionAnalyzer to export population statistics, and exposing them to ActivityClassifier. Implement as a separate experiment (Phase 6E.3).

3. Track 56 (indoor close-up / camera zoom) is the hardest failure to address without optical flow or camera motion compensation. Defer to Phase 6E.4 or later.

**Do NOT raise RUN_THRESHOLD** as a primary fix (Candidate C). This is threshold tuning without ground truth and violates the constraint against blind tuning.
