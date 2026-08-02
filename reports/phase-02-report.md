# Phase 2 Report — Video Ingestion & Preprocessing Pipeline

**Date Started:** 2026-07-30  
**Status:** 🔄 In Progress

---

## Objectives

Build the most reliable video ingestion and preprocessing pipeline possible, before any AI logic is introduced. Every later intelligence module depends on this pipeline being deterministic, memory-efficient, and correct.

**Success Criteria:**
- [ ] Accept all supported formats reliably (MP4, AVI, MOV, MKV, WEBM)
- [ ] Reject corrupted or unsupported files gracefully with structured errors
- [ ] Extract all video metadata accurately via FFmpeg
- [ ] Produce identical frame extraction results on repeated runs with the same settings
- [ ] Process 24-hour videos without excessive memory usage (target: < 2GB RSS)
- [ ] Log detailed preprocessing metrics in `StageResult`
- [ ] Pass all 10 benchmark test cases

---

## Features Implemented

*(To be filled at phase completion)*

- [ ] `utils/ffmpeg.py` — FFmpeg subprocess wrapper
- [ ] `utils/video_meta.py` — Full metadata extraction (fps, codec, resolution, brightness, motion)
- [ ] `utils/storage.py` — Upload storage with path conventions
- [ ] `engines/perception/frame_extractor/extractor.py` — Configurable frame extraction
- [ ] `pipeline/stages/s01_upload.py` — Real upload validation
- [ ] `pipeline/stages/s02_extract.py` — Real frame extraction stage
- [ ] `api/v1/routes/upload.py` — Multipart upload endpoint
- [ ] `services/upload_service.py` — Upload business logic
- [ ] Unit tests for all preprocessing utilities
- [ ] Benchmark results for all 10 test cases

---

## Benchmarks

*(To be filled at phase completion)*

| Test Case | Accepted | Metadata Accurate | Processing Time | Peak Memory | Pass |
|---|---|---|---|---|---|
| 01_empty_room.mp4 | - | - | - | - | - |
| 02_single_person.mp4 | - | - | - | - | - |
| 03_multiple_people.mp4 | - | - | - | - | - |
| 04_low_light.mp4 | - | - | - | - | - |
| 05_camera_shake.mp4 | - | - | - | - | - |
| 06_rain.mp4 | - | - | - | - | - |
| 07_vehicle.mp4 | - | - | - | - | - |
| 08_long_24hr_sample.mp4 | - | - | - | - | - |
| 09_corrupted.mp4 | REJECT | - | - | - | - |
| 10_variable_fps.mp4 | - | - | - | - | - |

**Frame extraction determinism:** *(confirmed / not yet tested)*  
**Average extraction speed:** *(fps)*  
**Peak memory (24hr video):** *(MB)*

---

## Known Issues

*(To be filled during implementation)*

---

## Resolved Bugs

*(To be filled during implementation)*

---

## Architectural Decisions

*(To be filled during implementation)*

---

## Future Improvements

*(To be filled at completion)*
