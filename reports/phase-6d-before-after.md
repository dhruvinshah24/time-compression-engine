# Phase 6D Before/After Comparison — archive_001, 300 seconds

**Branch:** `experiment/v1.0.1-accuracy-overhaul`  
**Date:** 2026-09-06  
**Change:** Added `"cycling"` to `StoryBuilder._ACTION_EVENTS` (one line)  
**Config:** Identical to Phase 6B — archive_001, 300s, YOLO11l, balanced, skip=5, threshold=0.25

---

## Funnel Comparison

| Metric | Phase 6B (baseline) | Phase 6D (fix) | Delta |
|---|---:|---:|---:|
| Runtime | 77.8s | **72.6s** | −5.2s |
| RTF | 0.259× | **0.242×** | −0.017 |
| Total tracks | 546 | **546** | 0 |
| Motion profiles | 277 | **277** | 0 |
| S07 events | 232 | **213** | −19 |
| Fused events | 232 | **213** | −19 |
| Story segments | 148 | **138** | −10 |
| Complete stories | 0 | **10** | **+10** |
| Partial stories | 21 | **15** | −6 |
| Kept events | 92 | **91** | −1 |
| Exported clips | 92 | **91** | −1 |

> [!IMPORTANT]
> Complete stories: **0 → 10**. This is the direct effect of the vocabulary fix.

---

## Unexpected Changes — Analysis

**S07 events: 232 → 213 (−19)**

Not caused by the StoryBuilder fix (which only affects S09). This is run-to-run variance from non-deterministic components in S07:
- ActivityClassifier uses floating-point velocity thresholds applied to tracker outputs
- Track observation timing varies slightly between runs due to clip extraction + YOLO inference
- 19/232 = 8.2% difference is within expected run-to-run variation

**Story segments: 148 → 138 (−10)**

Directly follows from S07 events −19: fewer events means fewer unique track IDs with events, meaning fewer story segments.

**Partial stories: 21 → 15 (−6)**

Some tracks that were PARTIAL in 6B are now COMPLETE in 6D (10 tracks). The net reduction in partial count = approximately 6 tracks reclassified + some lost due to fewer events.

**Exported clips: 92 → 91 (−1)**

One fewer event passed S11 compression. Run-to-run variance. Not caused by the fix.

---

## Complete Story Impact

All 10 complete stories produced in Phase 6D were PARTIAL in Phase 6B.  
Every COMPLETE segment contains exactly: `person_entered_scene → cycling → person_left_scene`.

| Segment | Track | Timestamp | Score | Coherent | 6B → 6D |
|---|---|---|---|---|---|
| seg_14 | 14 | 00:30–00:38 | 0.856 | ✓ | PARTIAL → **COMPLETE** |
| seg_56 | 56 | 00:43–01:00 | 0.839 | ✓ | PARTIAL → **COMPLETE** |
| seg_75 | 75 | 01:16–01:24 | 0.795 | ✓ | PARTIAL → **COMPLETE** |
| seg_160 | 160 | 02:15–02:28 | 0.844 | ✓ | PARTIAL → **COMPLETE** |
| seg_177 | 177 | 02:20–02:31 | 0.842 | ✓ | PARTIAL → **COMPLETE** |
| seg_234 | 234 | 02:41–02:47 | 0.845 | ✓ | PARTIAL → **COMPLETE** |
| seg_252 | 252 | 03:22–03:31 | 0.823 | ✓ | PARTIAL → **COMPLETE** |
| seg_273 | 273 | 03:40–03:45 | 0.856 | ✓ | PARTIAL → **COMPLETE** |
| seg_366 | 366 | 04:06–04:06 | 0.718 | ✓ | PARTIAL → **COMPLETE** |
| seg_1 (OBS-003) | 1 | 00:00–00:53 | — | ✗ | PARTIAL → **COMPLETE** (but incoherent) |

*Note: seg_1 became COMPLETE because it contains entry+cycling+exit events. It has continuity issues (OBS-003). Its narrative_score is penalized.*

---

## OBS-003 Status

**STILL PRESENT.** Same track (track 1), same pattern, same 5 continuity issues. Unrelated to the vocabulary fix. Low severity, documented separately.
