# Phase 4 Report — Multi-Object Tracking

## Phase Name
Multi-Object Tracking (Phase 4)

## Objectives
- Assign consistent Track IDs to physical objects across video frames
- Implement full track lifecycle: TENTATIVE → ACTIVE → LOST → ENDED
- Handle object entry/exit and brief occlusion (up to max_lost_frames)
- Ensure tracking results are independent of the detection model
- Pass all unit tests before integrating with real YOLO output

## Algorithm Implemented
**IoU-based Hungarian Matching with Track Lifecycle State Machine**

See `research/algorithms.md → Phase 4` for full rationale and alternative comparison.

### Key decisions:
- **Hungarian assignment** (not greedy nearest-neighbor): optimal O(n³) match, negligible for n<50
- **TENTATIVE state**: requires 2 consecutive matches before a track is confirmed — eliminates ghost tracks from noise detections
- **LOST state**: tracks survive up to `max_lost_frames` without a match — handles brief occlusion
- **IoU threshold 0.3**: standard SORT baseline — documented in config with directional tradeoff analysis

## Files Implemented

| File | Purpose |
|---|---|
| `engines/perception/tracker/config.py` | TrackerConfig with calibration notes |
| `engines/perception/tracker/track.py` | Track, TrackBBox, TrackObservation, TrackState |
| `engines/perception/tracker/iou.py` | compute_iou, compute_iou_matrix, hungarian_match |
| `engines/perception/tracker/tracker.py` | MultiObjectTracker engine |
| `pipeline/stages/s05_track.py` | Pipeline stage |
| `tests/unit/test_tracker.py` | Unit test suite |

## Test Results

```
35 tests — 35 passed, 0 failed
Run time: ~1.5s
```

### Key invariants tested:
- Same physical object always gets the same Track ID ✅
- Tentative tracks never confirmed without 2 consecutive matches ✅
- Tracks end after max_lost_frames without match ✅
- Two simultaneous people never swap IDs ✅
- Empty video produces zero tracks (no crash) ✅
- finalize() closes all open tracks ✅

## Benchmarks
*(Fill after running against real benchmark corpus)*

| Video | Tracks Created | Confirmed | Avg Track Length (frames) | Notes |
|---|---|---|---|---|
| 01_empty_room | — | — | — | Expecting 0 tracks |
| 02_single_person | — | — | — | Expecting 1 confirmed track |
| 03_multiple_people | — | — | — | Expecting 3–5 tracks |

## Configuration Defaults

| Parameter | Value | Rationale |
|---|---|---|
| iou_threshold | 0.3 | SORT standard baseline |
| max_lost_frames | 3 | ~0.6s tolerance at 5fps extracted |
| min_confirmation_frames | 2 | Eliminates single-frame false tracks |
| min_detection_confidence | 0.65 | Below main detection threshold |

## Known Issues
- None at implementation time.

## Upgrade Path (Phase 9)
- Mahalanobis distance + Kalman filter (SORT) for better occlusion handling
- ReID appearance embeddings (DeepSORT) for cross-occlusion re-identification
- No changes required to Track or TrackState data models

## Dependencies Added
- `scipy` (linear_sum_assignment) — added to requirements.txt
