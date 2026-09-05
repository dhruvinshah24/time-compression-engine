# FAIL-006 Diagnostic — archive_001 60s

**FAIL-006:** Insufficient track confirmation on real footage.

## TrackerConfig (current)

| Parameter | Value |
|---|---|
| min_confirmation_frames | 2 |
| min_detection_confidence | 0.65 |
| max_lost_frames | 3 |
| iou_threshold | 0.30 |

## Summary

| Metric | Value |
|---|---|
| Total person tracks | 23 |
| Confirmed | 1 |
| Unconfirmed | 22 |
| Confirmation rate | 4.3% |

## Observation Count Distribution

| Bin | Count |
|---|---|
| 1 obs | 10 |
| 2 obs | 1 |
| 3-5 obs | 1 |
| 6-10 obs | 1 |
| 11-20 obs | 7 |
| 21-49 obs | 3 |
| 50+ obs | 0 |

## Reason Breakdown (unconfirmed)

- **22 tracks**: ENDED_BEFORE_CONFIRMATION

## Alternate Threshold Comparison

| min_confirmation_frames | Tracks that would confirm |
|---|---|
| 1 | 23/23 |
| 2 | 13/23 ← CURRENT |
| 3 | 12/23 |
| 4 | 11/23 |
| 5 | 11/23 |
| 6 | 11/23 |
| 8 | 10/23 |
| 10 | 10/23 |
