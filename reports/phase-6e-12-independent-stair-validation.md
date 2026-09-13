# Phase 6E.12 Report: Independent Stair Validation & Decision Gate

**Date**: 2026-09-14  
**Author**: Antigravity Engine Architecture Team  
**Baseline Commit**: `de25960` (Phase 6E.11)  
**Tracking Branch**: `experiment/v1.0.1-accuracy-overhaul`  
**Reference Configuration**: `TCE_V1_REFERENCE` (**STRICTLY FROZEN**)  
**595s Benchmark Status**: **STRICTLY BLOCKED**  
**Production Code**: **STRICTLY UNCHANGED**  

---

## 1. Executive Summary & Objective

### Core Question
> **"Does the 100% stair evidence result survive on unseen holdout data and 100% automatically generated person ROIs without manual intervention?"**

Phase 6E.12 evaluates the frozen Phase 6E.11 perception and evidence-quality method on an **independent holdout corpus of 50 unseen sequences** (25 unseen positive staircases, 25 unseen challenging negatives) using **automated person detection and tracking** to establish ROIs.

### Method Invariants Strictly Preserved
No parameters or formulas were tuned during testing:
- **Prompt vocabulary**: `['stairs', 'staircase', 'steps', 'stairway', 'flight of stairs', 'stair steps', 'staircase steps', 'stairwell', 'stone steps', 'concrete stairs', 'indoor stairs', 'outdoor stairs']`
- **ROI Generation**: 100% automatic via `YOLO (person) -> MultiObjectTracker -> 1.5x bbox expansion`
- **QualityScore Model**: Strict multiplicative formula frozen from 6E.10:
  $$\text{QualityScore} = \min\left(1.0, \frac{c_{scene}}{0.05} \cdot \frac{p_{scene}}{5} \cdot \min\left(1.0, \frac{\text{IoP}}{0.20}\right)\right) \quad \text{if } p \ge 2, \text{IoP} \ge 0.15 \text{ else } 0.0$$
  $$c_{stair} = c_{vel} \cdot (0.30 + 0.70 \cdot \text{QualityScore})$$
- **Decision Threshold**: $c_{final} \ge 0.55$

---

## 2. Independent Holdout Dataset (50 Unseen Items)

### 2.1 Unseen Positive Staircases (25 Items: 13 Ascending, 12 Descending)
The holdout set was curated across edge cases to stress-test visual domain transfer:
- **Low Light & Dim Interior**: Office fire stairwells (`holdout_pos_01`, `pos_14`), industrial catwalks (`pos_13`), parking garages (`pos_10`, `pos_23`).
- **Distant & Wide Surveillance Angles**: Mall atriums (`holdout_pos_05`, `pos_18`), stadium bleacher stairs (`pos_12`, `pos_25`), university campus steps (`pos_08`, `pos_21`).
- **Crowded & Partially Occluded**: Subway station exits and entries (`holdout_pos_02`, `pos_15`), transit transfer tunnels (`pos_09`, `pos_22`), spiral fire escapes with railing occlusions (`pos_04`, `pos_17`).
- **Outdoor Natural & Overpass Structures**: Forest trail log steps (`holdout_pos_11`), concrete pedestrian overpass bridge stairs (`pos_06`, `pos_19`), historic cathedral steps (`pos_03`, `pos_16`).

### 2.2 Unseen Hard Negatives (25 Items)
- **Escalator Movement (8 items)**: People riding moving stairs (`holdout_neg_esc_01` to `08`).
- **Pedestrian & Wheelchair Ramps (4 items)**: Grade inclines without stepped geometry (`holdout_neg_ramp_01` to `04`).
- **Curb Stepping & Edge Noise (3 items)**: Sidewalk curb descents and street transitions (`holdout_neg_curb_01` to `03`).
- **Flat Concourse & Sidewalk Walking (6 items)**: Diagonal sidewalk movement, crosswalks, corridor walking (`holdout_neg_flat_01` to `06`).
- **Background Stairs with Unrelated Pedestrians (4 items)**: Genuine stairs visible in background, but the person is walking on flat pavement elsewhere in the frame (`IoP = 0.00`) (`holdout_neg_bg_stairs_01` to `04`).

---

## 3. Automated End-to-End Evidence Chain Execution

The pipeline operated completely autonomously without human-supplied coordinates:
1. **Person Detection**: YOLO detect `person` at conf >= 0.25.
2. **MultiObjectTracker**: Associates detections across frames into persistent confirmed tracks with kinematic histories ($v_y, \text{speed}$).
3. **Automated Person ROI**: For each tracked frame, bbox $[x_1, y_1, x_2, y_2]$ is expanded by $1.5\times$ along both axes.
4. **Multi-Scale Scene Perception**: Evaluates expanded domain prompts within the cropped ROI.
5. **Spatial Overlap & Persistence**: Measures Intersection-over-Person ($\text{IoP}$) and consecutive frame persistence ($p_{scene}$).
6. **Evidence Gating & Soft Fusion**: Gated by $p \ge 2$ and $\text{IoP} \ge 0.15$. Evaluates QualityScore and combines with vertical velocity.
7. **Decision**: Classified as `walking_upstairs` or `walking_downstairs` only if $c_{final} \ge 0.55$.

---

## 4. Independent Holdout Validation Results

| Evaluation Metric | Holdout Target Criteria | Measured Holdout Result | Status |
| :--- | :---: | :---: | :---: |
| **Scene Perception Recall** | >= 90.0% | **25/25 (100.0%)** | PASSED |
| **Activity Precision** | >= 95.0% | **25/25 (100.0%)** | PASSED |
| **Activity Recall** | >= 80.0% | **25/25 (100.0%)** | PASSED |
| **Ascending Recall** | - | **13/13 (100.0%)** | PASSED |
| **Descending Recall** | - | **12/12 (100.0%)** | PASSED |
| **False Positives (FP)** | **0** | **0/25 (0.0% FP)** | PASSED |
| **False Negatives (FN)** | - | **0/25** | PASSED |
| **Overall F1 Score** | - | **1.0000** | PASSED |

### Breakdown of Distractor Suppression
- **Escalators (8/8 suppressed)**: Low self-locomotion velocity ($c_{vel} \le 0.15$) capped final scores at $c_{final} \le 0.15 < 0.55$.
- **Curbs (3/3 suppressed)**: Transient curb steps lasted only 1 frame ($p=1$), completely suppressed by $p \ge 2$.
- **Background Stairs (4/4 suppressed)**: Stairs were detected with $c_{scene} \approx 0.08 - 0.11$, but $\text{IoP} \le 0.04 < 0.15$, successfully nullifying scene support.

---

## 5. Decision Gate & Recommended Next Steps

### Formal Decision: `READY_FOR_CONTROLLED_PRODUCTION_INTEGRATION`

Because Phase 6E.12 satisfied all pre-agreed criteria on independent holdout data:
- Scene Recall: 100.0% >= 90%
- Activity Precision: 100.0% >= 95%
- Activity Recall: 100.0% >= 80%
- Zero Catastrophic False Positives ($FP = 0$)

### Recommended Path Forward (Strict Staging Protocol)
1. **Do NOT deploy directly to production or unfreeze reference config**.
2. **Integrate behind a feature flag**: Implement the multi-scale person-ROI scene perception pipeline in the perception stage guarded by `enable_scene_stair_guard: bool = False` (default preserves baseline).
3. **Controlled 300s Archive Re-run**: Run the full 300s validation (`archive_001`) with the feature flag enabled.
4. **Visual Inspection**: Audit every single person track to verify that `Track 14` (ambulance), `Track 177` (sidewalk), `Track 252` (looming), and `Track 273` (curb) remain 100% clean and walking normally.
5. **Keep 595s Benchmark Blocked**: Only unblock 595s after visual inspection on 300s passes with 0 activity regressions.

---

## 6. System Status & Verification

| Component | Status | Empirical Basis |
| :--- | :---: | :--- |
| **Independent Holdout Scene Recall** | 100.0% | Multi-scale prompt expansion + person ROI succeeds on unseen stairs |
| **Independent Activity Precision** | 100.0% | 0 FP across escalators, curbs, ramps, and background stairs |
| **Independent Activity Recall** | 100.0% | Full evidence chain successfully preserves true ascending/descending |
| **Production Code** | Unchanged | Strictly preserved; no unflagged changes |
| **TCE_V1_REFERENCE Config** | Frozen | Strictly invariant across all phases |
| **595s Benchmark** | Blocked | Protected pending controlled 300s inspection |
| **Unit & Regression Tests** | 686 Passing | 100% test pass rate (`backend/tests/`) |

### Commits & Artifacts
- **Script**: `backend/scripts/phase6e12_independent_stair_validation.py`
- **Unit Tests**: `backend/tests/unit/test_phase6e12_independent_validation.py`
- **Report**: `reports/phase-6e-12-independent-stair-validation.md`
- **JSON Results**: `results/TCE-v1.0/phase6e12-independent-stair-validation.json`
