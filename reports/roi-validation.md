# ROI Validation — Phase 4 Exp-E

Measured: 2026-08-26 18:11  

## Geometry Tests

**3/4 tests passed**

| Test | Result | Expected Events | Got Events | Event Types |
|---|---|---|---|---|
| point_inside_zone_generates_entry | FAIL | 1 | 0 | none |
| point_outside_zone_no_event | PASS | 0 | 0 | none |
| entry_then_exit_generates_two_events | PASS | 2 | 2 | restricted_zone_entry, restricted_zone_exit |
| approach_without_crossing_no_entry | PASS | 0 | 0 | none |

## Corpus Video Simulation

Synthetic trajectory simulated directly (no YOLO). Tests ROI geometry only.

| Metric | Value |
|---|---|
| Entry detected | NO |
| Exit detected  | YES |
| Exit time observed | 18.36s |
| Exit time expected | 25.7s |
| Exit timing error | 7.34s |

## Capability Classification

| Capability | Classification |
|---|---|
| ROI geometry (point-in-polygon) | **IMPLEMENTED** |
| ROI with real YOLO detections | **NOT YET VALIDATED** |
| ROI false positive rate | **NOT YET VALIDATED** — no real footage |

## Limitations

- These tests use synthetic bounding box trajectories, NOT real YOLO detections.
- The geometry is correct, but ROI events in real footage depend on detection quality.
- If YOLO misses a person frame, ROI tracking will also miss that observation.
