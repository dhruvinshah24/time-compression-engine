# Pipeline Funnel — archive_001 59.99s

**Git commit:** `1ad97dd`  
**Model:** yolo11l  
**Resolution:** 320x240 @ 30.0fps  
**Measured:** 2026-09-06 00:11  

## Pipeline Funnel

```
  INPUT FRAMES                           1797
       ↓
  SELECTED FRAMES                        142
       ↓
  SCENE SEGMENTS                         N/A
       ↓
  FRAMES WITH DETECTIONS                 126
       ↓
  TOTAL DETECTIONS (all class)           360
       ↓
  TOTAL TRACKS                           67
       ↓
  PERSON TRACKS                          23
       ↓
  CONFIRMED TRACKS                       28
       ↓
  MOTION PROFILES                        28
       ↓
  SEMANTIC EVENTS                        13
       ↓
  FUSED EVENTS                           33
       ↓
  STORY SEGMENTS                         15
       ↓
  KEPT SEGMENTS                          13
       ↓
  EXPORTED EVENTS                        0
```

## Event Types Generated

- `cycling`
- `person_entered_scene`
- `person_left_scene`
- `person_reaching_up`
- `running`
- `walking_upstairs`

## Performance

| Metric | Value |
|---|---|
| Video duration | 59.99s |
| Total pipeline | 15.2s |
| RTF | 0.254x |
| Real-time | True |

## Stage Timings

| Stage | Duration (ms) | Success |
|---|---|---|
| s01_upload | 101 | True |
| s02_extract | 314 | True |
| s03_scene_detect | 1606 | True |
| s04_object_detect | 7128 | True |
| s05_track | 719 | True |
| s06_motion_analyze | 4 | True |
| s07_event_understand | 2179 | True |
| s08_confidence_fuse | 2 | True |
| s09_story_build | 3 | True |
| s10_rank | 2 | True |
| s11_summarize | 1 | True |
| s12_export | 3102 | True |
