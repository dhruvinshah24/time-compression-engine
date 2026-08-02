# Phase 7 Report — Confidence Fusion

## Phase Name
Confidence Fusion (Phase 7)

## Objectives
- Replace single-dimensional event confidence with a multi-dimensional vector
- Preserve all 5 signal dimensions for downstream analysis and calibration
- Make fusion weights configurable (not hardcoded)
- Support multiple fusion strategies for experimental comparison
- Filter events below fused threshold without silently discarding metadata
- Provide calibration statistics for the evaluation chapter

## Pre-Phase 7 Additions (per mentor guidance)

### 1. Event dependencies field
Every Event now carries:
```python
event.dependencies = [
    "track_7",
    "rule_rule_person_walking",
    "motion_profile_7",       # only when profile exists
]
```
This creates an explicit, auditable provenance chain from every event back through the pipeline. Answers "why was this event generated?" at the data level, not just in comments.

### 2. Rule confidence on EventRule
Each rule in the knowledge base now declares `rule_confidence`:
- `rule_person_running`: 0.88 (specific — fast speed is unambiguous)
- `rule_person_loitering`: 0.85 (specific — duration threshold makes it precise)
- `rule_object_appeared`: 0.65 (general — any class, more noise)

These priors inform Phase 7's rule dimension without requiring training data.

## Algorithm Implemented
**5-Dimensional Weighted Fusion with Configurable Strategy**

### The five dimensions:

| Dimension | Source | Meaning |
|---|---|---|
| `detection` | `track.avg_confidence` | How sure was the object detector? |
| `motion` | `motion_profile.motion_confidence` | How reliable is the motion analysis? |
| `rule` | `rule.rule_confidence` | How specific/reliable is the fired rule? |
| `track_stability` | `track.total_frames_matched` | How long and continuous was the track? |
| `scene_reliability` | Camera motion overlap fraction | How clean was the scene? |

**Why not a single average?**
Different signals have different failure modes. Detection confidence drops in low light. Motion confidence drops for short tracks. Keeping them separate lets Phase 10 identify which signal is most predictive per benchmark video.

### Default weights:
```
w_detection      = 0.30   # primary signal
w_motion         = 0.25   # quality of phase 5 output
w_rule           = 0.20   # domain knowledge prior
w_track_stability = 0.15  # temporal reliability
w_scene_reliability = 0.10 # environmental quality
```

### Fusion strategies (swappable via system_settings):
- `weighted_linear` (default): `Σ(w_i × c_i)`
- `geometric`: `Π(c_i^w_i)` — more sensitive to low individual dimensions
- `harmonic`: Weighted harmonic mean — most penalises weak dimensions
- `min`: Overall score = weakest dimension score

## Files Implemented

| File | Purpose |
|---|---|
| `engines/semantic/confidence_fusion/config.py` | FusionConfig with weight validation |
| `engines/semantic/confidence_fusion/fusion.py` | ConfidenceFuser, ConfidenceVector, FusionResult |
| `pipeline/stages/s08_confidence_fuse.py` | Pipeline stage |
| `tests/unit/test_confidence_fusion.py` | Unit + integration test suite |

## Test Results

```
29 tests — 29 passed, 0 failed
(233 total including all previous phases)
Run time: 1.95s total
```

### Integration tests (full 4-stage chain):

| Test | Chain | Expected | Result |
|---|---|---|---|
| Walking person → fused confidence | Track → Motion → Event → Fusion | Valid ConfidenceVector | ✅ |
| All 5 dimensions present | Full chain | All keys in vector | ✅ |
| Camera motion → lower scene_reliability | Same track + camera frames | scene_reliability reduced | ✅ |
| Dependencies traceable | Full chain | track_, rule_, motion_profile_ in deps | ✅ |

## ConfidenceVector data contract (for Phase 8):

```python
event.evidence["confidence_vector"] = {
    "detection": 0.85,
    "motion": 0.78,
    "rule": 0.83,
    "track_stability": 0.70,
    "scene_reliability": 1.0,
    "fused": 0.815,
    "weights_used": {...},
    "strategy": "weighted_linear",
}
event.confidence = 0.815   # updated to fused value
```

## Calibration Statistics (for Evaluation Chapter)

FusionResult.to_metrics_dict() provides:
- `avg_fused_confidence` — mean across all events
- `min_fused_confidence` / `max_fused_confidence` — range
- `dimension_means` — average per dimension (identifies weak signal sources)
- `total_discarded` — how many events were filtered

These statistics are saved to `reports/benchmarks/` after each benchmark run.

## Known Issues / Limitations
- `track_stability` uses `total_frames_matched / full_stability_frames` as a proxy.
  It doesn't account for total lost frames across the track's lifetime (not stored yet).
  More precise tracking metrics planned for Phase 10 (Evaluation).
- Default weights (0.30/0.25/0.20/0.15/0.10) are intuition-based priors.
  Empirical calibration on the benchmark corpus will follow in Phase 10.
- `rule_confidence` values in the knowledge base are manually assigned.
  Could later be learned from precision/recall data per rule type.

## Dependencies Added
- None. Pure NumPy (already in requirements.txt from Phase 4).
