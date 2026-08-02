# Benchmark Test Corpus — Time Compression Engine

This directory contains the **standard test corpus** used across all phases.

Using the same video set for every phase allows objective comparison of improvements over time.  
Every algorithm is validated against these 10 cases before moving to the next phase.

---

## Test Cases

| File | Scenario | Duration | Domain | Key Challenge |
|---|---|---|---|---|
| `01_empty_room.mp4` | Static scene, no events | 1 hour | CCTV | Extreme compression, no false positives |
| `02_single_person.mp4` | One person, simple events | 30 min | CCTV | Basic event detection baseline |
| `03_multiple_people.mp4` | 3–5 simultaneous people | 30 min | CCTV | Object tracking, event disambiguation |
| `04_low_light.mp4` | Night / dim lighting | 30 min | CCTV | Detection under adverse conditions |
| `05_camera_shake.mp4` | Unstable/shaky camera | 10 min | Dashcam | False scene-change rejection |
| `06_rain.mp4` | Precipitation on lens | 30 min | Outdoor CCTV | Noise filtering |
| `07_vehicle.mp4` | Vehicle arrival/departure | 20 min | Parking/Dashcam | Vehicle tracking |
| `08_long_24hr_sample.mp4` | Full-day recording | 24 hours | CCTV | Memory efficiency, chunked processing |
| `09_corrupted.mp4` | Intentionally damaged file | N/A | Any | Graceful rejection, clear error message |
| `10_variable_fps.mp4` | Non-standard FPS (1–60 fps) | 10 min | Any | FPS-independent frame extraction |

---

## Pass Criteria Per Phase

### Phase 2 (Ingestion & Preprocessing)
- [ ] `01–08`: Accepted, metadata extracted accurately
- [ ] `09`: Rejected gracefully with clear error in `StageResult.errors`
- [ ] `10`: FPS extracted correctly, frame skip calculated correctly
- [ ] `08`: Processed without OOM error (memory stays below 2GB RSS)

### Phase 3+ (Perception Engine)
- To be defined per phase.

---

## How to Populate the Test Corpus

These videos are **not committed to the repository**. Populate them locally:

```bash
# Option 1: Use your own recordings
# Copy files into this directory following the naming convention above.

# Option 2: Download public domain CCTV datasets
# Recommended sources:
#   - VIRAT Video Dataset (viratdata.org)
#   - CAVIAR Dataset (homepages.inf.ed.ac.uk/rbf/CAVIARDATA1/)
#   - UA-DETRAC (detrac.sfo.net)

# Option 3: Generate synthetic test videos using FFmpeg
# 01_empty_room.mp4 — static noise
ffmpeg -f lavfi -i color=c=black:s=1920x1080:r=25 -t 3600 01_empty_room.mp4

# 09_corrupted.mp4 — truncated file for rejection testing
ffmpeg -f lavfi -i color=c=black:s=1280x720:r=25 -t 5 temp.mp4
# Then truncate: truncate -s 1024 temp.mp4 && mv temp.mp4 09_corrupted.mp4
```

---

## Result Tracking

After running the benchmark suite, record results in:
```
datasets/benchmarks/{phase}_{date}_results.json
```

Schema:
```json
{
  "phase": "Phase 2",
  "date": "2026-07-30",
  "system": "Time Compression Engine v0.2.0",
  "results": [
    {
      "test_case": "01_empty_room.mp4",
      "passed": true,
      "metadata_accuracy": "exact",
      "processing_time_s": 12.4,
      "peak_memory_mb": 184,
      "notes": ""
    }
  ]
}
```
