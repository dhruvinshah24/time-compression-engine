# Phase 6E.8 — Soft Stair Evidence Controlled Experiment Report

**Phase:** 6E.8  
**Date:** 2026-09-13  
**Baseline Commit:** `bdc4183` (Phase 6E.7)  
**Target Video / Corpora:**
- Negative: `archive_001` (300s window, 79 raw stair triggers, known audit tracks 14, 177, 252, 273, 56, 160)
- Positive: `stair_benchmark` (7 items: `pos_01` to `pos_07`, 108 frames, ascending & descending)
**Decision:** **B. SOFT EVIDENCE PROMISING BUT NEEDS CALIBRATION**  
**Production Status:** UNCHANGED  
**Frozen Config:** `TCE_V1_REFERENCE` strictly UNCHANGED  
**Tests:** 668 passed (7 new regression tests added)  
**Benchmark Status:** 595s remains BLOCKED  

---

## 1. Executive Summary

Phase 6E.7 proved that a **hard binary scene-context guard** ($P(\text{stair}) = 0$ if no stair box detected) is **UNSAFE** because zero-shot open-vocabulary models rarely produce high confidence on architectural backgrounds, causing a **100% false-negative rate** on real stair-climbing sequences.

Phase 6E.8 conducted a rigorous **controlled experiment** on actual TCE event generation, evaluating four distinct soft-evidence policies to determine whether scene context can serve as a continuous evidence signal without causing regressions.

### Key Empirical Findings:
1. **100% Negative False-Positive Suppression:**
   - On `archive_001` (300s), **all 79 false velocity stair triggers were completely suppressed** (100.0% suppression) under Policies B, C, and D.
   - Known false-positive tracks (Track 14 loading ambulance, Track 177 diagonal sidewalk walking, Track 252 walking toward camera, Track 273 curb movement) were suppressed from `walking_upstairs` to natural `walking` events.
2. **Positive Benchmark Retention & Directional Asymmetry:**
   - In `pos_01_man_ascending.ogv` (outdoor surveillance, authentic ascending), **the event survived with high confidence ($c=0.715 - 0.858$) across all soft-evidence policies**.
   - In `pos_03_muybridge_descending.gif` (studio sequence, authentic descending, $c_{\text{scene}}=0.019$), **survival was highly sensitive to policy formulation**: it survived under Policy C (Evidence Fusion, $c=0.624$) but was attenuated below $0.55$ under Policy B ($c=0.385$) and Policy D ($c=0.511$).
   - In `pos_02_muybridge_ascending.gif` (19th-century vintage sequence), zero-shot scene detection produced $0.000$, causing it to fall back to `walking`.
3. **Seamless Downstream Integration with Confidence Fusion (Stage s08):**
   - Testing with `ConfidenceFuser` confirmed that soft-evidence events flow naturally into Stage s08, yielding a valid 5-dimensional `ConfidenceVector` and surviving the fused confidence threshold ($0.8590 \ge 0.35$).
4. **Parameter Stability & Calibration Warning:**
   - A 48-point sensitivity sweep ($w_{\text{base}} \in [0.20, 0.50]$, $\tau_{\text{ref}} \in [0.03, 0.10]$, $\tau_{\text{act}} \in [0.50, 0.60]$) proved that **negative suppression is 100% stable**, but **subtle positive retention is sensitive to the reference calibration parameter $\tau_{\text{ref}}$**.

**Decision: B. SOFT EVIDENCE PROMISING BUT NEEDS CALIBRATION.** Soft evidence is architecturally validated and superior to both raw velocity and hard binary guards, but requires calibrated vision-language thresholds before production promotion.

---

## 2. Integration Architecture

### Conceptual Dataflow:
```
  [2D Centroid Tracking]              [Scene-Context Detector]
            │                                    │
    Velocity Profile                     Open-Vocabulary Box
  (mean_vy, mean_speed)                (conf, persistence, bbox)
            │                                    │
            ▼                                    ▼
┌───────────────────────────────────────────────────────────┐
│     ActivityClassifier Locomotion Evidence Fusion         │
│  c_stair = f(c_velocity, c_scene, persistence, distance)  │
│                                                           │
│  If c_stair >= 0.55:                                      │
│      emit "walking_upstairs" / "walking_downstairs"       │
│  Else:                                                    │
│      natural fallback to "walking" or "running"           │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│     Stage s07 (Event Understanding / Narrative Pass 7)    │
│  Enriches Event with explicit explainability payload:     │
│  - velocity_confidence, scene_stair_confidence,           │
│    persistence, spatial_relation, fallback_label         │
└─────────────────────────────┬─────────────────────────────┘
                              │
                              ▼
┌───────────────────────────────────────────────────────────┐
│     Stage s08 (Confidence Fusion Engine)                  │
│  Evaluates 5-dimensional ConfidenceVector:                │
│  - detection, motion, rule, track_stability, scene_rel    │
│  Filters events where fused_confidence < 0.35             │
└───────────────────────────────────────────────────────────┘
```

### Architectural Rationale:
- **Smallest Correct Location:** Performing locomotion soft-evidence fusion inside `ActivityClassifier` allows false stair triggers to naturally fall back to `walking` or `running`. If stair events were emitted and subsequently discarded in Stage s08, the person track would have an unexplained gap in locomotion narrative.
- **Explainability Preservation:** The explicit evidence fields (`scene_stair_confidence`, `scene_stair_persistence`, `spatial_relation`) flow directly into `Event.evidence`, ensuring full visibility for auditing.
- **No Bypass of Stage s08:** Stage s08 continues to evaluate track stability, object detection quality, and optical-flow scene reliability on all events.

---

## 3. Evaluated Soft-Evidence Policies

| Policy | Mathematical Formulation | Design Intent |
|---|---|---|
| **Policy A: Baseline** | $c_{\text{stair}} = c_{\text{vel}}$ | Velocity-only classification (Phase 6D.4 baseline). |
| **Policy B: Soft-Multiplier** | $c_{\text{stair}} = c_{\text{vel}} \times \left(w_{\text{base}} + (1 - w_{\text{base}}) \cdot \min\left(1.0, \frac{c_{\text{scene}}}{\tau_{\text{ref}}}\right)\right)$<br>($w_{\text{base}}=0.30, \tau_{\text{ref}}=0.05, p \ge 2$) | Scaled multiplicative attenuation (Phase 6E.7 proposal). |
| **Policy C: Evidence-Fusion** | $c_{\text{stair}} = w_{\text{vel}} c_{\text{vel}} + w_{\text{scene}} \min\left(1.0, \frac{c_{\text{scene}}}{\tau_{\text{ref}}}\right) + w_{\text{pers}} \min\left(1.0, \frac{p_{\text{scene}}}{p_{\text{target}}}\right)$<br>($w=[0.50, 0.35, 0.15], p_{\text{target}}=5, p \ge 2$) | Multi-source linear confidence fusion across motion and scene. |
| **Policy D: Conservative Gate** | $c_{\text{stair}} = c_{\text{vel}} \times \left(w_{\text{base}} + (1 - w_{\text{base}}) \cdot \sqrt{\min\left(1.0, \frac{c_{\text{scene}}}{\tau_{\text{ref}}}\right)}\right)$<br>($w_{\text{base}}=0.35, \tau_{\text{ref}}=0.05, p \ge 2$) | Non-linear sub-linear boost for low non-zero detections. |

---

## 4. Actual Event-Level Experimental Results

### Summary Comparison Table:

| Metric | Policy A (Baseline) | Policy B (Soft-Multiplier) | Policy C (Evidence-Fusion) | Policy D (Conservative Gate) |
|---|---|---|---|---|
| **Negative Triggers (`archive_001`)** | 79 | 79 | 79 | 79 |
| **Negative Suppressed Count** | 0 / 79 | **79 / 79** | **79 / 79** | **79 / 79** |
| **Negative Suppression Rate** | **0.0%** | **100.0%** | **100.0%** | **100.0%** |
| **Positive Video Retained (`pos_01`–`03`)** | 3 / 3 (100.0%) | 1 / 3 (33.3%) | **2 / 3 (66.7%)** | 1 / 3 (33.3%) |
| **Positive Total Retained (`pos_01`–`07`)** | 3 / 7 (42.9%) | 1 / 7 (14.3%) | **2 / 7 (28.6%)** | 1 / 7 (14.3%) |
| **Known Audit Track 14 (Ambulance)** | FAILED (False Stair) | **PASSED (Walking)** | **PASSED (Walking)** | **PASSED (Walking)** |
| **Known Audit Track 177 (Sidewalk)** | FAILED (False Stair) | **PASSED (Walking)** | **PASSED (Walking)** | **PASSED (Walking)** |
| **Known Audit Track 252 (Pedestrian)** | FAILED (False Stair) | **PASSED (Walking)** | **PASSED (Walking)** | **PASSED (Walking)** |
| **Known Audit Track 273 (Curb Noise)** | FAILED (False Stair) | **PASSED (Walking)** | **PASSED (Walking)** | **PASSED (Walking)** |

---

## 5. Negative Footage Suppression Breakdown

Across the 79 false triggers in `archive_001`:
- **56 False Upstairs triggers:** 100% suppressed.
- **23 False Downstairs triggers:** 100% suppressed.

### Detailed Audit of Known Failure Tracks:

| Track ID | Scenario / Cause | Raw $c_{\text{vel}}$ | Scene $c_{\text{scene}}$ | Persistence | Policy B $c_{\text{final}}$ | Policy C $c_{\text{final}}$ | Final Decision |
|---|---|---|---|---|---|---|---|
| **Track 14** | Officers loading ambulance (vertical depth movement) | 0.733 | 0.000 | 0 | 0.2199 | 0.3665 | `walking (suppressed)` |
| **Track 177** | Sidewalk pedestrian walking diagonally away | 0.746 | 0.000 | 0 | 0.2238 | 0.3730 | `walking (suppressed)` |
| **Track 252** | Pedestrian crossing street toward camera | 0.712 | 0.000 | 0 | 0.2136 | 0.3560 | `walking (suppressed)` |
| **Track 273** | Pedestrian near curb; single-frame noise hit | 0.727 | 0.153 | 1 | 0.2181 | 0.3635 | `walking (suppressed)` |
| **Tracks 307, 482, 496, 511** | Transient single-frame background hits ($c \approx 0.15$) | ~0.710 | ~0.155 | 1 | ~0.213 | ~0.355 | `walking (suppressed)` |
| **Remaining 71 Tracks** | Urban pedestrian locomotion on flat pavement | 0.65–0.75 | 0.000 | 0 | 0.19–0.22 | 0.32–0.37 | `walking (suppressed)` |

*Crucial Persistence Insight:* Track 273 had a single-frame false alarm at frame 1335 ($c=0.153$). Requiring persistence $p_{\text{scene}} \ge 2$ successfully neutralizes this noise, preventing it from bypassing the guard.

---

## 6. Positive Benchmark Retention & Directional Breakdown

| Item ID | Media Type | Action / Direction | Raw $c_{\text{vel}}$ | Scene $c_{\text{scene}}$ | Persistence | Policy B Outcome | Policy C Outcome |
|---|---|---|---|---|---|---|---|
| `pos_01` | Outdoor video | Ascending (up) | 0.715 | **0.099** | 31 | **RETAINED** ($c=0.715$) | **RETAINED** ($c=0.858$) |
| `pos_02` | Studio sequence | Ascending (up) | 0.716 | 0.000 | 0 | Suppressed ($c=0.215$) | Suppressed ($c=0.358$) |
| `pos_03` | Studio sequence | Descending (down) | 0.681 | **0.019** | 5 | Suppressed ($c=0.385$) | **RETAINED** ($c=0.624$) |
| `pos_04`–`pos_07` | Static High-Res | Various | N/A | 0.00–0.02 | 0–1 | Static (no motion tracks) | Static (no motion tracks) |

### Directional Analysis:
- **Ascending Locomotion:**
  - Negative: 56/56 suppressed (100%).
  - Positive Video: 1/2 retained (50.0% — `pos_01` passed; `pos_02` studio sequence failed scene detection).
- **Descending Locomotion:**
  - Negative: 23/23 suppressed (100%).
  - Positive Video: 1/1 retained under Policy C (`pos_03` survived at $c=0.624$ due to linear persistence fusion); 0/1 under Policy B.

---

## 7. Parameter Sensitivity & Calibration Stability

A full factorial grid of 48 parameter configurations was evaluated:
- $w_{\text{base}} \in [0.20, 0.30, 0.40, 0.50]$
- $\tau_{\text{ref}} \in [0.03, 0.05, 0.08, 0.10]$
- $\tau_{\text{act}} \in [0.50, 0.55, 0.60]$

### Stability Findings:
1. **Negative Suppression Stability:**
   - Negative suppression remained **100.0% across all 48 parameter variations**.
   - Maximum velocity confidence in negative footage is $0.746$. Even with $w_{\text{base}} = 0.50$, $0.746 \times 0.50 = 0.373 < 0.50$.
   - **Conclusion:** Negative suppression is exceptionally robust and virtually immune to small parameter perturbations.
2. **Positive Retention Stability:**
   - `pos_01` ($c_{\text{scene}}=0.099$) retained **100.0% across all 48 parameter variations**.
   - `pos_03` ($c_{\text{scene}}=0.019$) is highly sensitive: under multiplicative models, it requires $\tau_{\text{ref}} \le 0.03$ or linear fusion (Policy C) to survive.
   - **Conclusion:** While the core outdoor surveillance scenario is stable, calibration on subtle/distant staircases requires further tuning with a broader positive dataset.

---

## 8. Explainability Payload

Every generated locomotion event carries a full, auditable evidence trail:

```json
{
  "event_type": "walking_upstairs",
  "track_id": 1,
  "confidence": 0.715,
  "evidence": {
    "person_label": "Person 1",
    "velocity_confidence": 0.715,
    "scene_stair_confidence": 0.099,
    "scene_stair_persistence": 31,
    "scene_stair_supported": true,
    "spatial_relation": "contained (IoU=0.28)",
    "final_stair_confidence": 0.715,
    "decision": "walking_upstairs",
    "fallback_label": "walking",
    "confidence_vector": {
      "detection": 0.8800,
      "motion": 0.7800,
      "rule": 0.7500,
      "track_stability": 1.0000,
      "scene_reliability": 1.0000,
      "fused": 0.8590
    }
  }
}
```

---

## 9. Failure Cases and Limitations

1. **Vintage / Studio Visual Domain Gap (`pos_02`):**
   - 19th-century black-and-white studio sequences lack modern architectural textures, causing zero-shot CLIP/YOLO-World to output $0.000$.
2. **Static Photographic Ground Truth (`pos_04`–`pos_07`):**
   - Still images lack temporal frame sequences, preventing velocity profile computation.
3. **Low-Confidence Descending Stairs (`pos_03`):**
   - In descending sequences where the camera perspective compresses step risers, scene confidence drops to $\sim 0.02$. Multiplicative models attenuate this unless combined with linear persistence fusion.

---

## 10. Status, Commitments & Decision

### Commitments:
- Production code: **UNCHANGED**.
- Reference config `TCE_V1_REFERENCE`: **FROZEN**.
- Test suite: **668 passing** (`pytest backend/tests/ -q` executed in 17.75s).
- Full-length benchmark (595s): **BLOCKED**.

### Decision: **B. SOFT EVIDENCE PROMISING BUT NEEDS CALIBRATION**
- Soft evidence is **empirically validated as vastly superior to hard binary guards** (100% negative suppression with genuine positive retention).
- However, coefficients ($w_{\text{base}}, \tau_{\text{ref}}, w_{\text{pers}}$) require domain calibration on a larger positive corpus before promotion into the frozen reference baseline.
