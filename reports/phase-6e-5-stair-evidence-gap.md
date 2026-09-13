# Phase 6E.5 — Stair Activity Capability & Evidence-Gap Diagnostic Report

**Phase:** 6E.5  
**Date:** 2026-09-13  
**Baseline Commit:** `f9bc309` (Phase 6E.4)  
**Target Video:** `archive_001` (`WhenYouA1948_512kb.mp4`, 300s validation window)  
**Decision:** **B. EXISTING SIGNALS INSUFFICIENT**  
**Production Status:** UNCHANGED  
**Frozen Config:** `TCE_V1_REFERENCE` strictly UNCHANGED  
**Benchmark Status:** 595s remains BLOCKED  

---

## 1. Executive Summary & Research Objective

In Phase 6E.4, bounding-box posture gating was empirically **refuted**: 2D bounding boxes naturally exhibit 7%–15% height and aspect ratio jitter on flat terrain, completely overlapping with false stair classifications.

Phase 6E.5 addresses the fundamental architectural question:
> **Can stair activity be inferred from the existing temporal pose, track kinematics, motion, and scene evidence in TCE? If not, what is the exact observable information gap?**

### Key Diagnostic Conclusion:
**B. EXISTING SIGNALS INSUFFICIENT.**  
The current TCE architecture does not possess the physical observables necessary to separate stair locomotion from flat-ground walking under perspective projection.
1. `pose_temporal.py` operates purely on lateral centroid displacement ($\Delta x$) and bounding-box ratios. It possesses **zero** measurement of leg elevation, foot placement, knee angles, or vertical gait oscillation.
2. The empirical distribution of temporal pose states across `CURRENT_STAIR_CLASSIFIER_POSITIVES` is **statistically identical** to non-stair tracks (e.g., 31.6% vs 26.3% walking, 29.1% vs 31.6% standing, 24.1% vs 21.1% running).
3. Under monocular perspective projection, walking away from or toward the camera on flat ground produces screen-space vertical velocities ($v_y$) and directional persistences that are mathematically and observationally indistinguishable from stair climbing across every existing TCE signal.
4. Production code remains strictly **UNCHANGED**.

---

## 2. Existing Temporal Pose Capability Audit

An exhaustive inspection of `backend/app/utils/pose_temporal.py` and its integration into Stage S07 Pass 3b was conducted.

### Available State Machine Outputs:
`TemporalPoseAnalyzer` uses a hysteresis-gated state machine with 9 defined states:
- `STANDING`: $h \ge 0.20$ frame height
- `WALKING`: $\Delta x \ge 0.005$ frame width / frame
- `RUNNING`: $\Delta x \ge 0.020$ frame width / frame
- `LOWERING`: transitional body height drop $> 0.03$ over 3 frames
- `CROUCHING`: $h < 0.18$ frame height
- `CRAWLING`: $h < 0.15 \land \Delta x \ge 0.003$
- `FALLEN`: $w/h \ge 1.8 \land h < 0.12$
- `SITTING`: handled in `activity_state_machine.py` via chair proximity; not emitted by `pose_temporal`
- `UNKNOWN`: insufficient frames / ambiguous geometry

### Kinematic & Anatomical Observables Audit:
| Kinematic Feature | Captured by TCE Pose? | Integration Status in S07 | Notes |
|---|---|---|---|
| **Knee elevation / flexion** | **NO (UNAVAILABLE)** | None | Bbox does not resolve knee joints |
| **Hip elevation / vertical oscillation** | **NO (UNAVAILABLE)** | None | Centroid $y$ conflates body lift with terrain slope |
| **Alternating leg motion** | **NO (UNAVAILABLE)** | None | Only lateral ankle spread in optional S07 Pass 3 keypoints |
| **Body inclination / torso angle** | **NO (UNAVAILABLE)** | None | `torso_angle_deg` is `None` in bbox-based Pass 3b |
| **Periodic vertical body motion** | **NO (UNAVAILABLE)** | None | No Fourier/periodicity analysis on centroid or limbs |
| **Foot placement / step contact** | **NO (UNAVAILABLE)** | None | Foot-ground contact is unmeasured |
| **Relative limb motion** | **NO (UNAVAILABLE)** | None | Pass 3b uses bounding box only; keypoints bypassed |

**Conclusion:** The temporal pose system measures **lateral displacement** ($\Delta x$) and gross body aspect ratio. It does not measure vertical locomotion mechanics.

---

## 3. Evidence Matrix

Evaluation of whether existing TCE signals can support or contradict stair activity across observable physical human actions:

| Physical Activity | Centroid $v_y$ | Horiz $v_x$ | Speed $s$ | Bbox Height Var | Bbox Aspect Ratio | Temporal Pose | Track Duration | Directional Persistence | Scene Change Info | Camera Motion Signal | ROI Info | Object Co-occurrence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Walking Upstairs** | **SUPPORTS** ($v_y < 0$) | AMBIGUOUS | SUPPORTS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | **SUPPORTS** ($>0.50$) | AMBIGUOUS | CONTRADICTS if tilt | UNAVAIL | UNAVAIL |
| **Walking Downstairs** | **SUPPORTS** ($v_y > 0$) | AMBIGUOUS | SUPPORTS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | **SUPPORTS** ($>0.50$) | AMBIGUOUS | CONTRADICTS if tilt | UNAVAIL | UNAVAIL |
| **Flat Walking (across screen)** | **CONTRADICTS** ($v_y \approx 0$) | SUPPORTS ($v_x \neq 0$) | SUPPORTS | AMBIGUOUS | AMBIGUOUS | SUPPORTS (`WALKING`) | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | UNAVAIL | UNAVAIL |
| **Running** | AMBIGUOUS | SUPPORTS ($v_x \gg 0$) | **CONTRADICTS** ($s \ge 0.08$) | AMBIGUOUS | AMBIGUOUS | **CONTRADICTS** (`RUNNING`) | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | UNAVAIL | UNAVAIL |
| **Walking toward camera** | **AMBIGUOUS (MIMICS DOWN)** | AMBIGUOUS ($v_x \approx 0$) | SUPPORTS | AMBIGUOUS | AMBIGUOUS | **AMBIGUOUS** (`STANDING`)* | AMBIGUOUS | **MIMICS DOWN** ($>0.50$) | AMBIGUOUS | AMBIGUOUS | UNAVAIL | UNAVAIL |
| **Walking away from camera** | **AMBIGUOUS (MIMICS UP)** | AMBIGUOUS ($v_x \approx 0$) | SUPPORTS | AMBIGUOUS | AMBIGUOUS | **AMBIGUOUS** (`STANDING`)* | AMBIGUOUS | **MIMICS UP** ($>0.50$) | AMBIGUOUS | AMBIGUOUS | UNAVAIL | UNAVAIL |
| **Diagonal walking** | **MIMICS UP / DOWN** | SUPPORTS ($v_x \neq 0$) | SUPPORTS | AMBIGUOUS | AMBIGUOUS | SUPPORTS (`WALKING`) | AMBIGUOUS | **MIMICS STAIRS** ($>0.50$) | AMBIGUOUS | AMBIGUOUS | UNAVAIL | UNAVAIL |
| **Curb stepping** | AMBIGUOUS | AMBIGUOUS | SUPPORTS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | **CONTRADICTS** (transient) | AMBIGUOUS | AMBIGUOUS | UNAVAIL | UNAVAIL |
| **Loading / unloading (e.g. gurney)** | **MIMICS UP / DOWN** | AMBIGUOUS | SUPPORTS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | AMBIGUOUS | UNAVAIL | AMBIGUOUS (Vehicle near) |

*\*Note: When walking directly toward or away from the camera, lateral displacement $\Delta x \approx 0 < 0.005$, causing `pose_temporal` to classify the person as `STANDING`, even while walking.*

---

## 4. Analysis of Known Ground-Truth Audit Tracks

We re-evaluated the known audit tracks from Phase 6D.5–6E.4 to determine what information TCE actually possesses for each:

| Track ID | True Physical Action | Raw Label | Raw Stair Conf | Dominant Pose | Final Pose | Pose Sequence | Can ANY Existing Signal Distinguish Visual Ground Truth from Stairs? |
|---|---|---|---|---|---|---|---|
| **14** | Responders loading ambulance | **walking_upstairs** | 0.733 | RUNNING | RUNNING | RUNNING $\to$ LOWERING $\to$ WALKING $\to$ RUNNING $\to$ STANDING | **NO.** Moving around vehicle gurney creates vertical centroid fluctuation. Vehicle co-occurrence is present but does not inhibit stair logic. |
| **56** | Doctor examining patient | running | 0.000 | LOWERING | LOWERING | WALKING $\to$ RUNNING $\to$ WALKING $\to$ STANDING $\to$ LOWERING | **N/A.** Stair classifier did not fire ($v_y$ was non-directional). Speed triggered running false positive. |
| **160** | Traffic officer / pedestrians | running | 0.000 | WALKING | RUNNING | WALKING $\to$ RUNNING $\to$ WALKING $\to$ LOWERING $\to$ STANDING | **N/A.** Stair classifier did not fire. Speed triggered running false positive. |
| **177** | Pedestrians walking away | **walking_upstairs** | 0.746 | STANDING | STANDING | STANDING $\to$ WALKING $\to$ RUNNING $\to$ STANDING $\to$ LOWERING | **NO.** Pure perspective retreat. Person moves directly away in depth $\implies v_y < 0$ and $\Delta x \approx 0$. |
| **252** | Pedestrian crossing intersection | **walking_upstairs** | 0.800 | STANDING | RUNNING | STANDING | **NO.** Diagonal crosswalk heading creates steady upward screen-space drift with directional persistence 0.67. |
| **273** | Pedestrian crossing intersection | **walking_upstairs** | 0.727 | WALKING | RUNNING | WALKING | **NO.** Diagonal crosswalk trajectory creates sustained vertical displacement across 12 observations. |

---

## 5. Temporal Pose Correlation with `CURRENT_STAIR_CLASSIFIER_POSITIVES`

Across all 98 confirmed person tracks with $\text{obs} \ge 5$:
- **79 tracks** triggered raw stair classification (`CURRENT_STAIR_CLASSIFIER_POSITIVES`).
- **19 tracks** were non-stair tracks.

### Empirical Pose Distribution Comparison:
| Pose State Metric | CURRENT_STAIR_CLASSIFIER_POSITIVES ($N=79$) | Non-Stair Tracks ($N=19$) | Statistical Finding |
|---|---|---|---|
| **Dominant: STANDING** | 23 (**29.1%**) | 6 (**31.6%**) | Virtually identical |
| **Dominant: WALKING** | 25 (**31.6%**) | 5 (**26.3%**) | Virtually identical |
| **Dominant: RUNNING** | 19 (**24.1%**) | 4 (**21.1%**) | Virtually identical |
| **Dominant: CROUCHING** | 7 (**8.9%**) | 1 (**5.3%**) | Minor noise variation |
| **Dominant: LOWERING** | 2 (**2.5%**) | 1 (**5.3%**) | Minor noise variation |
| **Dominant: UNKNOWN / OTHER** | 3 (**3.8%**) | 2 (**10.5%**) | Minor noise variation |
| **Final: WALKING** | 23 (**29.1%**) | 4 (**21.1%**) | Overlapping |
| **Final: STANDING** | 10 (**12.7%**) | 3 (**15.8%**) | Overlapping |
| **Final: RUNNING** | 17 (**21.5%**) | 6 (**31.6%**) | Overlapping |

### State Sequence Analysis:
- In stair positives, **40 out of 79 tracks (50.6%)** have empty state sequences `()`, meaning the state never transitioned after initial hysteresis confirmation.
- The state sequences show chaotic switching (e.g. `['RUNNING', 'WALKING']`, `['STANDING', 'WALKING', 'RUNNING']`) caused by bounding-box tracker jitter, not structured biomechanical phases.
- **Conclusion:** There is **no distinctive temporal pose signature** for stair positives.

---

## 6. Offline Existing-Signal Combination Experiments

We tested whether combining existing signals could create a defensible stair classification rule:

| Combination Rule | Passed Tracks | Upstairs | Downstairs | Reduction | Surviving Known Tracks | Evaluation Result |
|---|---|---|---|---|---|---|
| **Baseline Raw Stair** | 79 | 37 | 42 | 0.0% | [14, 177, 252, 273] | 100% false positive rate |
| **Combo 1:** Raw Stair $\land$ Dom Pose == `WALKING` | 25 | 11 | 14 | 68.4% | [273] | Arbitrary filter. Surviving 25 tracks are flat-ground pedestrians. Rejects 177 because walking away produced low $\Delta x$ (`STANDING`). |
| **Combo 2:** Raw Stair $\land$ Final Pose == `WALKING` | 23 | 13 | 10 | 70.9% | None | Rejects the 4 known tracks, but **23 other flat-ground pedestrians pass**. Still 100% false positives. |
| **Combo 3:** Raw Stair $\land$ Dom Pose $\in$ {`WALKING`, `RUNNING`} | 44 | 15 | 29 | 44.3% | [14, 273] | Retains known false positives; leaves 44 flat-ground tracks. |
| **Combo 4:** Raw Stair $\land$ Final Pose $\neq$ `STANDING` | 69 | 30 | 39 | 12.7% | [14, 252, 273] | Negligible effect; leaves 69 flat-ground tracks. |
| **Combo 5:** Raw Stair $\land$ Has Transition ($\text{len}(\text{seq}) \ge 1$) | 39 | 16 | 23 | 50.6% | [14, 177, 252, 273] | All known false positives survive. |
| **Combo 6:** Raw Stair $\land$ Dom Pose == `STANDING` | 23 | 13 | 10 | 70.9% | [177, 252] | Inverts logic (stair walking requires standing?). Survives 177 and 252. |

**Key Finding:** No combination of existing signals is defensible. Every combination either retains known false positives or merely selects a different arbitrary subset of flat-ground pedestrians.

---

## 7. Mathematical Information-Gap Analysis

Why can existing signals NEVER distinguish flat-ground walking from stair climbing?

### The Monocular Perspective Ambiguity:
In a camera with focal length $f$ and optical center at $(c_x, c_y)$, a point $(X, Y, Z)$ in 3D camera coordinates projects to image coordinates $(x, y)$:
$$x = f \frac{X}{Z} + c_x, \quad y = f \frac{Y}{Z} + c_y$$

Taking the time derivative of vertical screen position $y(t)$:
$$\frac{dy}{dt} = \frac{f}{Z} \frac{dY}{dt} - \frac{f \cdot Y}{Z^2} \frac{dZ}{dt}$$

Where:
- $\frac{dY}{dt}$ is the **true vertical world velocity** (physical elevation change, e.g., stairs).
- $\frac{dZ}{dt}$ is the **depth velocity** (walking toward or away from the camera).
- $Y$ is the vertical elevation relative to camera optical axis ($Y > 0$ when person is below the camera level, as in typical downward-pitched surveillance).

### The Inevitable False Positive:
When a person walks away from a camera on flat asphalt:
1. They have **zero** physical vertical velocity: $\frac{dY}{dt} = 0$.
2. They are moving away in depth: $\frac{dZ}{dt} > 0$.
3. Because $Y > 0$ (person is on the ground below camera height) and $f > 0$:
   $$\frac{dy}{dt} = 0 - \frac{f Y}{Z^2} \left(\frac{dZ}{dt}\right) < 0$$
4. A negative $\frac{dy}{dt}$ means the centroid **moves upward on the screen**.
5. `ActivityClassifier._detect_stairs()` measures **only** $\frac{dy}{dt} < -0.005$. It cannot determine whether $\frac{dy}{dt} < 0$ is caused by:
   - Climbing a physical staircase ($\frac{dY}{dt} < 0$), OR
   - Walking away along flat ground ($\frac{dZ}{dt} > 0$).

Without 3D scene geometry, camera pitch calibration, or explicit detection of a staircase object, **this ambiguity is mathematically unsolvable from 2D centroid kinematics**.

---

## 8. Decision Gate

### Decision: **B. EXISTING SIGNALS INSUFFICIENT**
The current TCE signals and architecture cannot distinguish stair activity from perspective-induced motion.

---

## 9. Minimum Missing Capability & Next Experiment

### Minimum Missing Capabilities:
To responsibly classify stair activity without hallucinating flat-ground walking, TCE requires at least one of the following two missing observables:
1. **Scene Context / Staircase Affordance:** Explicit scene-level detection or segmentation of physical stairs, steps, or escalators in the scene (e.g., via open-vocabulary object detection `stairs`, `staircase`, `steps`, or semantic segmentation). If no stair structure exists in the scene, the stair activity classifier must be **inhibited**.
2. **Biomechanical 3D Pose Dynamics:** Tracking periodic vertical ankle/knee displacement relative to the hip (stair climbing exhibits distinct high-knee elevation and foot plant intervals, whereas flat walking exhibits predominantly horizontal ankle translation).

### Proposed Next Experiment (Phase 6E.6):
**Staircase Scene-Context Guard Diagnostic:**
- Test whether open-vocabulary detection (YOLO-World or existing detector) or a lightweight scene classifier can reliably verify the presence/absence of stairs in `archive_001` and benchmark clips.
- Until such scene context is established, **inhibit velocity-derived stair classification** by default when no staircase structure is detected, thereby eliminating 100% of flat-ground false positives without breaking downstream narrative and story pipelines.

---

## 10. Production Safety & Reference Status

- **Production Code:** Strictly **UNCHANGED**.
- **TCE_V1_REFERENCE:** Strictly **FROZEN**.
- **Unit Tests:** **661 passing** (17.12s).
- **595s Benchmark:** Strictly **BLOCKED**.
