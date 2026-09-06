# Pipeline Funnel — archive_001 300.0s

**Git commit (actual HEAD):** `3ba0660` (Phase 6A fixes applied)
**Note:** run_full_pipeline.py script shows `1ad97dd` in its header (cached at script init time). Actual HEAD at execution time was `3ba0660`.
**Model:** yolo11l
**Resolution:** 320x240 @ 30.0fps
**Measured:** 2026-09-06 (Phase 6B)

## Pipeline Funnel

```
  INPUT FRAMES                           8991
       ↓
  SELECTED FRAMES                        780
       ↓
  SCENE SEGMENTS                         N/A
       ↓
  FRAMES WITH DETECTIONS                 678
       ↓
  TOTAL DETECTIONS (all class)           3366
       ↓
  TOTAL TRACKS                           546
       ↓
  PERSON TRACKS                          249
       ↓
  CONFIRMED TRACKS                       277
       ↓
  MOTION PROFILES                        277
       ↓
  SEMANTIC EVENTS                        92
       ↓
  FUSED EVENTS                           232
       ↓
  STORY SEGMENTS                         148
       ↓
  KEPT SEGMENTS                          92
       ↓
  EXPORTED EVENTS                        0
                                         [FAIL-009: script bug — pipeline generated 92 clips]
```

## Event Types Generated

- `cycling`
- `group_gathering`
- `light_turned_off`
- `light_turned_on`
- `person_crawling`
- `person_crouching_sustained`
- `person_entered_scene`
- `person_fallen`
- `person_left_scene`
- `person_picked_up_book`
- `person_placed_handbag`
- `person_sitting`
- `person_standing_up`
- `vehicle_approaching`
- `vehicle_receding`
- `vehicle_stationary`

## Performance

| Metric | Value |
|---|---|
| Video duration | 300.0s |
| Total pipeline | 77.8s |
| RTF | 0.259x |
| Real-time | True |

## Stage Timings

| Stage | Duration (ms) | Success |
|---|---|---|
| s01_upload | 94 | True |
| s02_extract | 1416 | True |
| s03_scene_detect | 8198 | True |
| s04_object_detect | 24000 | True |
| s05_track | 2479 | True |
| s06_motion_analyze | 29 | True |
| s07_event_understand | 11123 | True |
| s08_confidence_fuse | 8 | True |
| s09_story_build | 12 | True |
| s10_rank | 5 | True |
| s11_summarize | 2 | True |
| s12_export | 30332 | True |
