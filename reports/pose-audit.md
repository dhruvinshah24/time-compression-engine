# Temporal Pose Audit — Phase 5G

Measured: 2026-09-05 23:07  

## TemporalPoseAnalyzer Configuration

| Parameter | Default |
|---|---|
| track_id | <class 'inspect._empty'> |
| window_size | 20 |
| min_frames_crawling | 5 |
| min_frames_crouching | 3 |
| min_frames_running | 4 |
| min_frames_fallen | 2 |
| min_frames_sitting | 8 |
| hysteresis_frames | 2 |

## Pose Sequence Simulation

| Sequence | Duration | Events | Event Types |
|---|---|---|---|
| standing_30s | 30.0s | 0 | none |
| crouching_10s | 10.0s | 0 | none |
| crawling_10s | 10.0s | 1 | person_crouching_sustained |
| transition_full | 26.0s | 1 | person_crouching_sustained |

## Capability Classification

| Capability | Classification |
|---|---|
| STANDING | **IMPLEMENTED** |
| CROUCHING | **IMPLEMENTED** |
| CRAWLING | **IMPLEMENTED** |
| STATE_TRANSITIONS | **PARTIALLY_VALIDATED** |
| FALLEN | **IMPLEMENTED — NOT YET VALIDATED on suitable footage** |
| RUNNING | **IMPLEMENTED — NOT YET VALIDATED (requires real running footage)** |

## Important Notes

- These tests use synthetic bbox ratios, NOT real detected persons.
- Bbox-ratio-based pose detection is approximate.
- A real crouching/crawling person may not match these bbox ratios.
- No capability is PROVEN without real validated footage.
- Single-frame events are explicitly prevented by the hysteresis mechanism.
