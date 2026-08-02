# Datasets

This directory contains all video datasets used for development, testing, evaluation, and benchmarking of the Time Compression Engine.

**IMPORTANT:** Never commit raw video files to version control. Add large files to `.gitignore`.  
This directory structure is committed; the video content is not.

---

## Directory Structure

```
datasets/
├── raw/                    # Original, unprocessed source videos
│   ├── cctv/               # Static indoor/outdoor surveillance footage
│   ├── dashcam/            # Vehicle-mounted forward-facing cameras
│   ├── drone/              # Aerial footage
│   ├── wildlife/           # Fixed wildlife monitoring cameras
│   ├── construction/       # Site monitoring time-lapses and static feeds
│   └── lab/                # Controlled laboratory recordings
│
├── processed/              # Output of the preprocessing pipeline (Phase 2)
│   └── {JOB_ID}/           # One folder per processing job
│       ├── frames/         # Extracted keyframes
│       ├── metadata.json   # Extracted video metadata
│       └── stage_results/  # StageResult JSON per pipeline stage
│
├── annotations/            # Ground truth labels for evaluation (Phase 11)
│   └── {video_id}.json     # Annotated event timestamps + types
│
└── benchmarks/             # Benchmark result snapshots
    └── {date}_{description}/
```

---

## File Naming Convention

Raw videos should follow this naming convention:
```
{domain}_{location}_{date}_{sequence}.{ext}
```

Examples:
- `cctv_entrance_20260730_001.mp4`
- `dashcam_highway_20260730_001.mov`
- `construction_site_a_20260801_003.avi`

---

## Annotation Format (`annotations/{video_id}.json`)

```json
{
  "video_id": "uuid-here",
  "video_file": "cctv_entrance_20260730_001.mp4",
  "annotator": "human",
  "annotation_date": "2026-07-30",
  "events": [
    {
      "event_type": "person_entered",
      "start_time_ms": 29220000,
      "end_time_ms": 29232000,
      "confidence": 1.0,
      "objects": ["person"],
      "notes": "Individual entered from left door"
    }
  ]
}
```

---

## Supported Video Formats

| Format | Extension | Notes |
|---|---|---|
| MP4 (H.264/H.265) | `.mp4` | Preferred format |
| AVI | `.avi` | Legacy support |
| QuickTime | `.mov` | Common from cameras |
| Matroska | `.mkv` | High-quality captures |
| WebM | `.webm` | Web-sourced footage |

---

## Domain Coverage

Your evaluation dataset should ideally include footage from all supported domains:

| Domain | Typical Duration | Key Event Types |
|---|---|---|
| CCTV | 4–24 hours | person_entered, person_exited, parcel_delivered |
| Dashcam | 30 min–8 hours | vehicle_arrived, light_changed |
| Drone | 10 min–2 hours | object_moved, vehicle_arrived |
| Wildlife | 24–72 hours | object_appeared, object_removed |
| Construction | 8–24 hours | object_placed, object_moved |
| Laboratory | 1–8 hours | object_manipulated, light_changed |

---

## Adding New Datasets

1. Place raw file in the appropriate `raw/{domain}/` subfolder.
2. Follow the naming convention above.
3. Add a corresponding entry in `annotations/` if ground truth is available.
4. Update `benchmarks/` after running evaluation.
