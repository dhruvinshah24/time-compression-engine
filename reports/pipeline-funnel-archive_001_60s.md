# Pipeline Funnel — archive_001 59.99s

**Git commit:** `1ad97dd`  
**Model:** yolo11l  
**Resolution:** 320x240 @ 30.0fps  
**Measured:** 2026-09-05 23:35  

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
  CONFIRMED TRACKS                       1
       ↓
  MOTION PROFILES                        1
       ↓
  SEMANTIC EVENTS                        20
       ↓
  FUSED EVENTS                           20
       ↓
  STORY SEGMENTS                         10
       ↓
  KEPT SEGMENTS                          20
       ↓
  EXPORTED EVENTS                        0
```

## Event Types Generated

- `group_gathering`
- `light_turned_off`
- `light_turned_on`
- `person_entered_scene`
- `person_left_scene`
- `person_picked_up_book`
- `person_reaching_up`
- `person_walking`
- `running`

## Performance

| Metric | Value |
|---|---|
| Video duration | 59.99s |
| Total pipeline | 15.8s |
| RTF | 0.263x |
| Real-time | True |

## Stage Timings

| Stage | Duration (ms) | Success |
|---|---|---|
| s01_upload | 96 | True |
| s02_extract | 332 | True |
| s03_scene_detect | 1766 | True |
| s04_object_detect | 7384 | True |
| s05_track | 526 | True |
| s06_motion_analyze | 2 | True |
| s07_event_understand | 2143 | True |
| s08_confidence_fuse | 1 | True |
| s09_story_build | 2 | True |
| s10_rank | 1 | True |
| s11_summarize | 2 | True |
| s12_export | 3462 | True |
