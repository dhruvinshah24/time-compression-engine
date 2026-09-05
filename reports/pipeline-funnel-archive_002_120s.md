# Pipeline Funnel — archive_002 119.97s

**Git commit:** `1ad97dd`  
**Model:** yolo11l  
**Resolution:** 640x360 @ 24.0fps  
**Measured:** 2026-09-05 23:46  

## Pipeline Funnel

```
  INPUT FRAMES                           2876
       ↓
  SELECTED FRAMES                        163
       ↓
  SCENE SEGMENTS                         N/A
       ↓
  FRAMES WITH DETECTIONS                 140
       ↓
  TOTAL DETECTIONS (all class)           557
       ↓
  TOTAL TRACKS                           181
       ↓
  PERSON TRACKS                          41
       ↓
  CONFIRMED TRACKS                       0
       ↓
  MOTION PROFILES                        0
       ↓
  SEMANTIC EVENTS                        19
       ↓
  FUSED EVENTS                           19
       ↓
  STORY SEGMENTS                         9
       ↓
  KEPT SEGMENTS                          19
       ↓
  EXPORTED EVENTS                        0
```

## Event Types Generated

- `light_turned_off`
- `light_turned_on`
- `person_entered_scene`
- `person_left_scene`
- `person_reaching_up`
- `person_walking`

## Performance

| Metric | Value |
|---|---|
| Video duration | 119.97s |
| Total pipeline | 18.9s |
| RTF | 0.158x |
| Real-time | True |

## Stage Timings

| Stage | Duration (ms) | Success |
|---|---|---|
| s01_upload | 112 | True |
| s02_extract | 598 | True |
| s03_scene_detect | 2895 | True |
| s04_object_detect | 8425 | True |
| s05_track | 451 | True |
| s06_motion_analyze | 1 | True |
| s07_event_understand | 2345 | True |
| s08_confidence_fuse | 2 | True |
| s09_story_build | 2 | True |
| s10_rank | 2 | True |
| s11_summarize | 1 | True |
| s12_export | 4032 | True |
