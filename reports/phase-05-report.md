# Phase 5 Report — Motion Analysis

## Phase Name
Motion Analysis (Phase 5)

## Objectives
- Compute per-track velocity vectors from Phase 4 track observation histories
- Classify each track's dominant speed: stationary / slow / walking / fast
- Classify dominant direction: 8-compass (N/NE/E/SE/S/SW/W/NW)
- Detect approach/recede signal from bounding box area change
- Detect camera-motion-dominated frames (global coherent motion)
- Provide MotionProfile per confirmed track for Phase 6 (Semantic Event Understanding)

## Algorithm Implemented
**Centroid Velocity Estimation with Motion Classification**

See `research/algorithms.md → Phase 5` for full rationale.

### Key decisions:
- **Centroid-based** (not optical flow): Phase 4 track data is already structured —
  reprocessing raw pixels is unnecessary. Optical flow is reserved for Phase 9 (camera motion compensation where centroid is insufficient).
- **Area-change approach detection**: bbox growing = approaching; shrinking = receding.
  Threshold of 5% avoids triggering on bbox jitter.
- **Camera motion coherence**: if ≥85% of active track velocity vectors agree in direction,
  declare the frame camera-motion-dominated. Downstream stages suppress event generation for these frames.
- **Pure NumPy**: no OpenCV, no additional dependencies beyond what Phase 4 already required.

## Files Implemented

| File | Purpose |
|---|---|
| `engines/perception/motion_analyzer/config.py` | MotionAnalyzerConfig with calibration notes |
| `engines/perception/motion_analyzer/analyzer.py` | MotionAnalyzer engine, MotionProfile, VelocityObservation |
| `pipeline/stages/s06_motion_analyze.py` | Pipeline stage |
| `tests/unit/test_motion_analyzer.py` | Unit test suite |

## Test Results

```
31 tests — 31 passed, 0 failed
Run time: ~0.2s
```

### Key behaviours tested:
- Stationary track classified correctly ✅
- Walking track classified correctly ✅
- Approaching track has_approach_phase = True ✅
- Single-observation tracks excluded (no velocity pair) ✅
- Tentative tracks excluded ✅
- Camera motion coherence: coherent velocities → detected ✅
- Camera motion coherence: random velocities → not detected ✅
- Too few tracks → camera motion detection skipped ✅
- Empty track list → empty result, no crash ✅

## Benchmarks
*(Fill after running against real benchmark corpus)*

| Video | Tracks Analyzed | Stationary | Moving | Camera Motion Frames |
|---|---|---|---|---|
| 01_empty_room | — | — | — | 0 expected |
| 02_single_person | — | — | — | 0 expected |
| 05_camera_shake | — | — | — | Many expected |

## Speed Thresholds (defaults)

| Class | Range (normalized units/second) | Typical real-world mapping at 1080p |
|---|---|---|
| stationary | < 0.01 | < ~10px/s |
| slow | 0.01 – 0.05 | ~10–50px/s (slow walk or shuffle) |
| walking | 0.05 – 0.15 | ~50–160px/s (normal walking) |
| fast | ≥ 0.15 | > ~160px/s (running, vehicle) |

*These thresholds will be calibrated empirically against benchmark videos 02 and 03.*

## Phase 6 Integration Contract
Every confirmed track now has a MotionProfile in context:
```python
context.metadata["motion_profiles"][track_id] = MotionProfile(
    dominant_speed_class=SpeedClass.WALKING,
    dominant_direction=Direction.E,
    has_approach_phase=False,
    has_recede_phase=False,
    is_stationary=False,
    ...
)
```
Phase 6 (Semantic Event Understanding) reads these to classify events:
- person + WALKING → person_walking
- person + FAST → person_running
- car + APPROACHING → vehicle_approaching_camera
- person + STATIONARY (long duration) → potential_loitering

## Known Issues
- Camera motion detection requires ≥3 simultaneous confirmed tracks.
  Videos with only 1–2 objects will not trigger camera motion detection
  even if the camera is shaking. This is intentional conservatism.
  Enhancement target: Phase 9 (optical flow fallback for sparse scenes).

## Dependencies Added
- None. Pure NumPy.
