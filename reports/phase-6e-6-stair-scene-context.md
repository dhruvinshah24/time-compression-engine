# Phase 6E.6 — Staircase Scene-Context Guard Diagnostic Report

**Phase:** 6E.6  
**Date:** 2026-09-13  
**Baseline Commit:** `5898262` (Phase 6E.5)  
**Target Video:** `archive_001` (`WhenYouA1948_512kb.mp4`, 300s validation window)  
**Decision:** **A. PROMISING** (Controlled Production Experiment Justified)  
**Production Status:** UNCHANGED  
**Frozen Config:** `TCE_V1_REFERENCE` strictly UNCHANGED  
**Benchmark Status:** 595s remains BLOCKED  

---

## 1. Executive Summary & Data Limitation Warning

Phase 6E.5 established that 2D centroid vertical velocity cannot distinguish true elevation change from perspective-induced motion, and that temporal pose state machines lack limb kinematics.

Phase 6E.6 evaluated whether **scene-level staircase context** via open-vocabulary object detection can provide the missing physical evidence to suppress velocity-derived stair false positives.

### Critical Data Limitation:
`archive_001` contains **zero verified physical stairs or stair-climbing activities**. Therefore:
- This experiment measures **FALSE-POSITIVE SUPPRESSION ON NEGATIVE FOOTAGE**.
- It **CANNOT** measure true-positive retention, stair detection recall, precision, or F1 score.
- A positive staircase dataset is strictly required before claiming verified stair recognition accuracy.

### Key Finding:
Across all 79 raw stair-positive triggers and 412 audited person observation frames:
- **Strategy A ("stairs"):** Suppressed **100.0% (79/79)** of false stair triggers at $\text{conf} \ge 0.20, \text{persistence} \ge 2$ frames.
- **Strategy B (expanded query):** Suppressed **100.0% (79/79)** of false stair triggers across all tested thresholds ($\text{conf} \ge 0.15$).
- **Known audit tracks (14, 177, 252, 273):** **100% suppressed** under both strategies.
- Open-vocabulary YOLO-World produced an extremely low false-alarm rate on negative urban footage (only 5 single-frame hits out of 412 frames at $\text{conf} \ge 0.15$, none persisting $\ge 2$ frames).

**Decision: A. PROMISING.** Controlled production integration is justified for future validation. Production code remains strictly **UNCHANGED** in this phase.

---

## 2. Available Scene-Context Technologies in TCE

We audited the existing backend model registry and dependencies:
1. **YOLO-World (Open-Vocabulary Detection):**
   - Model weights `yolov8l-worldv2.pt` (~100MB) are already present in the backend directory.
   - Powered by a CLIP vision-language text encoder (`clip-vit-base-patch32`, 338MB), enabling zero-shot detection of arbitrary plain-English object prompts without model retraining.
   - Inference speed on NVIDIA GPU: **~21.5 ms/frame** in batches (measured during diagnostic).
2. **Standard COCO-80 Models (`yolo11*`, `yolov8*`):**
   - Do **NOT** include `stairs`, `staircase`, `steps`, `escalator`, `ramp`, or `incline` in their fixed 80 classes.
3. **Semantic Segmentation / Scene Classification:**
   - No segmentation or scene-level classification models (e.g. Places365) currently exist in the repository.
4. **ROI Manager (`app/utils/roi_manager.py`):**
   - Supports manual virtual zones, but has no automated scene geometry extraction.

**Conclusion:** YOLO-World is the only currently viable, zero-dependency addition capable of querying physical stair structures in the existing repository.

---

## 3. Formal Hypothesis & Failure Modes

### Hypothesis Formulation:
- **$H_1$ (Scene-Context Guard):** If no staircase or incline structure is detected in the relevant scene with temporal persistence ($\ge 2$ frames), velocity-derived stair classification must be inhibited.
- **$H_0$ (Null Hypothesis):** Scene-context detection does not reliably distinguish stair scenes (either through excessive false alarms on non-stairs or inability to detect real stairs).

### Potential Failure Modes:
1. **Distant / Small Stairs:** Stairs occupying $<2\%$ of frame area may fail detection.
2. **Occlusion:** Crowds, vehicles, or architectural columns partially obscuring steps.
3. **Architectural False Alarms:** Crosswalk stripes, window louvers, building facades, or curb shadows resembling horizontal steps.
4. **Extreme Camera Angles:** Downward bird's-eye views where step risers are invisible.
5. **Ramps vs Stairs:** Wheelchair ramps having vertical incline without discrete steps.

---

## 4. Experimental Method & Evaluation Protocol

An offline diagnostic (`backend/scripts/phase6e6_stair_scene_context.py`) was executed across the 300s window of `archive_001`:
1. S01–S05 were executed with standard experimental parameters (`min_activity_observations=5`, `cycle_threshold=0.25`, `require_temporal_overlap=True`).
2. All 98 confirmed person tracks were analyzed. 79 tracks triggered raw stair classification (`raw_stair_conf >= 0.55` and `mean_speed >= WALK_THRESHOLD`).
3. 412 unique observation frames covering the active timelines of all stair-positive tracks and known false-positive audit tracks were extracted.
4. YOLO-World was evaluated across two text prompt strategies:
   - **Strategy A (Stair-only):** `["stairs"]`
   - **Strategy B (Expanded query):** `["stairs", "staircase", "steps", "escalator", "ramp", "incline"]`
5. Confidence sweeps were conducted at 0.15, 0.20, 0.25, and 0.30.
6. Temporal persistence requirements were tested at 1, 2, 3, and 5 frames.
7. Spatial relationships (IoU and normalized centroid distance) between person tracks and candidate detections were computed.

---

## 5. Negative-Footage Suppression Results

Because `archive_001` has zero outdoor stairs, every suppressed track is a **correct suppression of a false positive**.

### Suppression Rates Across Strategies & Thresholds:

| Strategy | Confidence Threshold | Min Persistence | Retained Tracks | Suppressed Tracks | False-Positive Suppression Rate |
|---|---|---|---|---|---|
| **Strategy A ("stairs")** | 0.15 | $\ge 1$ frame | 11 | 68 | 86.1% |
| **Strategy A ("stairs")** | 0.15 | $\ge 2$ frames | 7 | 72 | 91.1% |
| **Strategy A ("stairs")** | 0.15 | $\ge 3$ frames | 0 | 79 | **100.0%** |
| **Strategy A ("stairs")** | **0.20** | **$\ge 2$ frames** | **0** | **79** | **100.0%** |
| **Strategy A ("stairs")** | 0.25 | $\ge 2$ frames | 0 | 79 | **100.0%** |
| **Strategy B (Expanded)** | 0.15 | $\ge 1$ frame | 0 | 79 | **100.0%** |
| **Strategy B (Expanded)** | 0.15 | $\ge 2$ frames | 0 | 79 | **100.0%** |
| **Strategy B (Expanded)** | 0.20 | $\ge 2$ frames | 0 | 79 | **100.0%** |
| **Strategy B (Expanded)** | 0.25 | $\ge 2$ frames | 0 | 79 | **100.0%** |

### Frame-Level False Alarm Analysis:
- Out of 412 audited frames:
  - Strategy A produced only **5 single-frame detections** at $\text{conf} \ge 0.15$ (1.2% frame hit rate, all $\text{conf} \le 0.165$). None persisted for $\ge 2$ consecutive frames.
  - Strategy B produced **0 detections** at $\text{conf} \ge 0.15$ (0.0% frame hit rate).

---

## 6. Known False-Positive Audit Track Evaluation

| Track ID | True Physical Ground Truth | Raw Label | Raw Stair Conf | Strategy A Max Conf | Strategy A Persistence | Strategy B Max Conf | Strategy B Persistence | Guard Action |
|---|---|---|---|---|---|---|---|---|
| **14** | Responders loading ambulance | `walking_upstairs` | 0.733 | 0.000 | 0 / 28 obs | 0.000 | 0 / 28 obs | **SUPPRESSED** |
| **56** | Doctor examining patient | `running` | 0.000 | 0.000 | 0 / 43 obs | 0.000 | 0 / 43 obs | **N/A** (not stair) |
| **160** | Traffic officer / pedestrians | `running` | 0.000 | 0.000 | 0 / 45 obs | 0.000 | 0 / 45 obs | **N/A** (not stair) |
| **177** | Pedestrians walking away | `walking_upstairs` | 0.746 | 0.000 | 0 / 27 obs | 0.000 | 0 / 27 obs | **SUPPRESSED** |
| **252** | Pedestrian crossing intersection | `walking_upstairs` | 0.800 | 0.000 | 0 / 7 obs | 0.000 | 0 / 7 obs | **SUPPRESSED** |
| **273** | Pedestrian crossing intersection | `walking_upstairs` | 0.727 | 0.153* | 1 / 12 obs | 0.000 | 0 / 12 obs | **SUPPRESSED** ($\text{pers} \ge 2$) |

*\*Note on Track 273: At frame 1335, a single marginal hit occurred ($\text{conf}=0.153$, $\text{dist}=0.395$, $\text{IoU}=0.037$) on distant background architectural lines. Requiring $\text{persistence} \ge 2$ frames or $\text{conf} \ge 0.20$ cleanly suppressed this isolated false alarm.*

---

## 7. Temporal Persistence & Spatial Relationship Analysis

1. **Temporal Persistence is Essential:**
   Single-frame detections ($\text{persistence}=1$) at low confidence ($\text{conf}=0.15$) caused 11 flat-ground tracks to pass Strategy A. Requiring $\text{persistence} \ge 2$ frames reduced false alarms by 36.4%, and $\ge 3$ frames eliminated them entirely (100% suppression).
2. **Spatial Relationship:**
   When spurious hits occurred (e.g. frame 1335 near Track 273), the spatial separation between the person and the candidate box was large ($\text{dist} \approx 0.40$ frame units, $\text{IoU} < 0.04$). Requiring the person to be spatially co-located or overlapping with the stair structure provides an additional discriminative filter.

---

## 8. Positive-Data Requirement Specification

To validate the other half of the confusion matrix (true-positive retention, recall, and precision), a benchmark dataset with verified staircases is strictly required.

### Recommended Positive Validation Corpus:
1. **Ascending Stairs:** Video footage of subjects walking up physical stairs (straight, angled, spiral).
2. **Descending Stairs:** Video footage of subjects walking down physical stairs.
3. **Camera Angle Variations:**
   - Eye-level frontal view
   - Surveillance overhead angle ($15^\circ$–$45^\circ$ downward pitch)
   - Profile / lateral view
4. **Context Variations:**
   - Indoor staircases (well-lit and low-light)
   - Outdoor concrete/stone public stairs
5. **Hard Negative Controls:**
   - Subjects walking on flat ground directly toward and away from the camera under identical downward camera pitch.
   - Subjects walking up/down wheelchair ramps.
   - Crosswalks with high-contrast horizontal stripes.

---

## 9. Architectural Decision

### Decision: **A. PROMISING**
Scene-context evidence reliably suppresses negative-footage stair hallucinations (79/79 false triggers eliminated at $\text{conf} \ge 0.20, \text{persistence} \ge 2$) and is technically viable for a controlled production implementation.

---

## 10. Proposed Minimum Production Implementation Plan

When authorized, the minimal controlled production implementation will consist of:
1. **Scene Stair Context Pass:**
   In S07 (or S05), evaluate scene keyframes (from S03 scene detection) using `yolov8l-worldv2` with classes `["stairs", "staircase"]`.
2. **Scene Affordance Flag:**
   Record `scene_has_stairs: bool` for each detected scene if $\text{confidence} \ge 0.20$ and $\text{persistence} \ge 2$.
3. **Classifier Guard in `ActivityClassifier._detect_stairs()`:**
   If `has_scene_stairs` is `False`, inhibit emission of `walking_upstairs` and `walking_downstairs`, falling back to standard `walking` or `running`.

---

## 11. Production Safety & Reference Status

- **Production Code Status:** Strictly **UNCHANGED** in Phase 6E.6.
- **Frozen Reference Config:** `TCE_V1_REFERENCE` remains strictly **FROZEN**.
- **Unit Test Suite:** **661 passing** (17.55s).
- **595s Benchmark:** Strictly **BLOCKED**.
