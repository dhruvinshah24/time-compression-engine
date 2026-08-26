# Phase 3 Validation Report
# Time Compression Engine v1.0.1-accuracy-overhaul
# Generated: 2026-08-26

## Summary

This report classifies every TCE capability as one of:
- **PROVEN** — demonstrated on real hardware with real input and measurable output
- **PARTIALLY VALIDATED** — tested with real processing but without ground truth
- **IMPLEMENTED** — code exists, unit tests pass, not yet run on real footage
- **NOT YET VALIDATED** — code written but no real-footage or integration test yet

The rule is: **do not claim a capability works merely because code exists or a unit test passes.**

---

## System Facts (PROVEN)

All of the following were directly measured on the development machine.

| Fact | Value | Date |
|---|---|---|
| GPU | NVIDIA GeForce RTX 5050 Laptop GPU (Blackwell, CC 12.0) | 2026-08-25 |
| VRAM | 8.55 GB total, 7.41 GB free at idle | 2026-08-25 |
| CUDA | 13.2 | 2026-08-25 |
| PyTorch | 2.13.0+cu132 | 2026-08-25 |
| Python | 3.14.5 | 2026-08-25 |
| Ultralytics | 8.4.96 | 2026-08-25 |
| OpenCV | 5.0.0 | 2026-08-25 |
| YOLO11n FPS | 80 FPS @ 1080p | 2026-08-25 |
| YOLO11s FPS | 57 FPS @ 1080p | 2026-08-25 |
| YOLO11m FPS | 40 FPS @ 1080p | 2026-08-25 |
| YOLO11l FPS | 32 FPS @ 1080p | 2026-08-25 |
| YOLO11x FPS | 32 FPS @ 1080p | 2026-08-25 |
| SAHI speedup | 1.18× vs sequential batch | 2026-08-25 |
| Quality analysis | ~65ms per 1080p frame | 2026-08-25 |
| End-to-end: 45s video | Processed in 49s | 2026-08-26 |

---

## Capability Classification

### Core Pipeline

| Capability | Classification | Evidence |
|---|---|---|
| Frame extraction via FFmpeg | **PROVEN** | 45s video processed 2026-08-26, confirmed on disk |
| Quality analysis per frame | **PROVEN** | 65ms measured with test benchmark 2026-08-25 |
| Low-light detection (CLAHE + gamma) | **PARTIALLY VALIDATED** | low_light_ratio=0.045 measured on synthetic video |
| UNUSABLE frame skipping | **PARTIALLY VALIDATED** | unusable_ratio=0.045 measured on synthetic video |
| YOLO11x object detection | **PARTIALLY VALIDATED** | detections observed on synthetic video; precision/recall not measured |
| SAHI sliced inference | **PARTIALLY VALIDATED** | 1.18× speedup measured; accuracy improvement not quantified |
| Multi-person tracking | **IMPLEMENTED** | Track data observed in pipeline runs; ID-switch rate not measured |
| ReID across gaps | **IMPLEMENTED** | Code present; no validation with known track identities |
| ROI zone crossing detection | **PARTIALLY VALIDATED** | Events generated in pipeline run; no ground truth to compare |
| Event confidence fusion | **IMPLEMENTED** | Scores computed; calibration not measured |
| Story / narrative building | **IMPLEMENTED** | Summaries generated; content quality not evaluated |
| Export (thumbnails, clips) | **PROVEN** | Thumbnail 15,887 bytes confirmed; clip 664,306 bytes confirmed |
| Evidence API chain | **PROVEN** | All 6 API endpoints confirmed 200 on 2026-08-26 |

### Phase 3 Additions

| Capability | Classification | Evidence |
|---|---|---|
| Adaptive skip — pre-extraction streaming | **IMPLEMENTED** | 16 unit tests pass (synthetic video with OpenCV); NOT run on real CCTV |
| Event protection guard | **IMPLEMENTED** | 8 unit tests pass; NOT wired into real pipeline run |
| Temporal pose state machine | **IMPLEMENTED** | 12 unit tests pass (synthetic pose sequences); NOT validated on labelled activities |
| YOLO11x-pose integration | **NOT YET VALIDATED** | Model name added to profile; benchmarked FPS: not yet measured |
| Diagnostics API | **IMPLEMENTED** | Route added; not yet tested with real job IDs in staging |
| Evaluation matrix framework | **IMPLEMENTED** | 9 unit tests pass; no real-footage evaluation records yet |
| Model profile selector (UI) | **IMPLEMENTED** | Backend wired; frontend component not yet validated end-to-end |
| VIRAT dataset convention | **NOT YET VALIDATED** | Metadata schema defined; video not downloaded |

---

## Known Failures

| ID | Description | Classification |
|---|---|---|
| FAIL-001 | Synthetic white rectangle not detected by YOLO11x | EXPECTED — ACCEPTED |
| FAIL-002 (expected) | Temporal pose thresholds are estimates, not calibrated | ACCEPTED — documented |
| FAIL-003 (expected) | Crawling detection at desk (false positive risk) | KNOWN LIMITATION — documented in pose_temporal.py |

---

## Capabilities NOT YET CLAIMED (Deferred)

The following capabilities are NOT claimed in this release, because real-footage
evidence has not been gathered:

- Crawling detection accuracy on real footage
- Running detection F1 score
- Low-light detection improvement (with/without preprocessing) on real footage
- Adaptive skip frame selection quality (important frames not missed)
- Multi-person ID-switch rate
- Long-video (≥30min) processing stability
- VIRAT dataset results (awaiting download)

---

## Next Steps

1. Download VIRAT Ground Dataset → place in `data/real/virat/raw/`
2. Run `backend/scripts/run_validation.py --video VIRAT_S_000001.mp4`
3. Record results in `data/real/virat/metadata/VIRAT_S_000001.yaml`
4. Update this report with real detection/tracking numbers
5. Benchmark YOLO11x-pose FPS (add to GPU benchmark script)
6. Run low-light benchmark on 4 illumination levels
7. Progressive scaling test (30s → 5min → 30min)

---

## Test Suite

| Metric | Value |
|---|---|
| Total tests | 518/518 passing (as of 2026-08-26) |
| New tests in Phase 3 | 46 |
| Test failures | 0 |
| Tests requiring real footage | 0 (all use synthetic input) |
