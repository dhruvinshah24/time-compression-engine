# Pipeline Funnel — archive_001 300.0s

**Git commit:** `1ad97dd`  
**Model:** yolo11l  
**Resolution:** 320x240 @ 30.0fps  
**Measured:** 2026-09-05 23:45  

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
  CONFIRMED TRACKS                       5
       ↓
  MOTION PROFILES                        5
       ↓
  SEMANTIC EVENTS                        32
       ↓
  FUSED EVENTS                           82
       ↓
  STORY SEGMENTS                         40
       ↓
  KEPT SEGMENTS                          32
       ↓
  EXPORTED EVENTS                        0
```

## Event Types Generated

- `group_gathering`
- `light_turned_off`
- `light_turned_on`
- `person_entered_scene`
- `person_left_scene`
- `person_sitting`
- `person_standing_up`

## Performance

| Metric | Value |
|---|---|
| Video duration | 300.0s |
| Total pipeline | 53.1s |
| RTF | 0.177x |
| Real-time | True |

## Stage Timings

| Stage | Duration (ms) | Success |
|---|---|---|
| s01_upload | 106 | True |
| s02_extract | 1433 | True |
| s03_scene_detect | 8269 | True |
| s04_object_detect | 24927 | True |
| s05_track | 628 | True |
| s06_motion_analyze | 3 | True |
| s07_event_understand | 11442 | True |
| s08_confidence_fuse | 4 | True |
| s09_story_build | 3 | True |
| s10_rank | 2 | True |
| s11_summarize | 1 | True |
| s12_export | 6154 | True |
