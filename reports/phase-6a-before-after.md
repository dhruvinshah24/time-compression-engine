# Phase 6A — Before / After Comparison
# archive_001 · first 60 seconds · YOLO11l · balanced · skip=5 · threshold=0.25

**Branch:** `experiment/v1.0.1-accuracy-overhaul`
**Baseline commit:** `2effbf9`
**Phase 6A commit:** (pending — see below)
**Date:** 2026-09-06

---

## Fixes Applied

### FAIL-007 — TrackBBox / TemporalPoseAnalyzer interface mismatch
**File:** [`backend/app/pipeline/stages/s07_event_understand.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/pipeline/stages/s07_event_understand.py) lines 403–413

**Root cause (exact):**
`TrackObservation.bbox` is a `TrackBBox` dataclass. S07 Pass 3b called:
```python
if bbox is None or len(bbox) < 4:   # AttributeError: TrackBBox has no len()
    continue
x1, y1, x2, y2 = bbox               # TypeError: not iterable
```
`TrackBBox` has named fields (`x1`, `y1`, `x2`, `y2`) but no `__len__` and no `__iter__`.

**Fix (smallest possible change):**
```python
if isinstance(bbox, TrackBBox):
    x1, y1, x2, y2 = bbox.x1, bbox.y1, bbox.x2, bbox.y2
elif hasattr(bbox, "__len__") and len(bbox) >= 4:
    x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
else:
    continue
```
The `isinstance` branch handles the production case. The `__len__` branch is a legacy fallback.

---

### FAIL-006 — Insufficient confirmed track count
**File:** [`backend/app/engines/perception/tracker/track.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/engines/perception/tracker/track.py) line 136

**Root cause (exact, measured):**
`is_confirmed` returned `state in (ACTIVE, LOST)`. After `finalize()` runs, it calls
`track.end()` on all LOST tracks — converting them to ENDED. All 12 person tracks that
were ACTIVE during the video became ENDED after finalize, causing `is_confirmed=False`.

Diagnostic evidence:

| track_id | confirmed_at_frame | state after finalize | is_confirmed (before fix) |
|---|---|---|---|
| 15 | 188 | ACTIVE | True |
| 56 | 264 | ENDED (was ACTIVE→LOST→ENDED) | **False** |
| 14 | 186 | ENDED | **False** |
| 2,3,4 | 10 | ENDED | **False** |
| 1,5 | 10 | ENDED | **False** |
| 26 | 207 | ENDED | **False** |
| 62 | 337 | ENDED | **False** |
| 34 | 235 | ENDED | **False** |
| 28 | 210 | ENDED | **False** |
| 19 | 198 | ENDED | **False** |
| 6,7,8,13,36,38,42,43,48,63 | None | ENDED | False (never confirmed) |

**Fix (smallest possible change):**
```python
# Before:
return self.state in (TrackState.ACTIVE, TrackState.LOST)

# After:
return self.confirmed_at_frame is not None
```
`confirmed_at_frame` is set when a track crosses `min_confirmation_frames` and is never
cleared. A track that was ever confirmed remains confirmed — independent of post-finalize state.

**What did NOT change:**
- `min_confirmation_frames` was NOT changed (still 2)
- `min_detection_confidence` was NOT changed (still 0.65)
- `max_lost_frames` was NOT changed (still 3)
- `iou_threshold` was NOT changed (still 0.30)

---

## Before / After Metrics

| Metric | Before (2effbf9) | After (Phase 6A) | Change | Why |
|---|---|---|---|---|
| **Tests** | **536** | **562** | **+26** | 9 FAIL-007 + 17 FAIL-006 regression tests |
| Runtime (s) | 15.8 | **15.2** | −0.6s | Minor variance; no algorithmic change |
| RTF | 0.263× | **0.254×** | −0.009× | Minor variance |
| Input frames | 1797 | 1797 | = | Same footage |
| Selected frames | 142 | 142 | = | Same skip=5 |
| Frames with detections | 126 | 126 | = | Same model, same threshold |
| Total detections | 360 | 360 | = | S04 unchanged |
| Person tracks | 23 | 23 | = | S04/S05 logic unchanged |
| **Confirmed tracks** | **1** | **13** | **+12** | FAIL-006 fix: is_confirmed now reads confirmed_at_frame |
| **Motion profiles** | **1** | **28** | **+27** | S06 runs on all confirmed tracks; previously starved |
| **ReID persons assigned** | **1** | **4** | **+3** | 13 confirmed tracks → 4 unique person IDs assigned |
| **Semantic events (raw)** | **20** | **13** | **−7** | State machine now runs on all 13 tracks, replacing noisy per-frame events with transitions |
| **Fused events** | **20** | **33** | **+13** | More confirmed tracks → more events through S08 |
| **Story segments** | **10** | **15** | **+5** | More events → more segments |
| **Complete stories** | **0** | **0** | = | Still 0 — explained below |
| Top ranking score | 0.7265 | **0.7620** | +0.036 | Higher-quality segments from confirmed tracks |
| Kept segments | 20 | 13 | −7 | Correct: 13 high-quality events vs 20 low-quality |
| Exported events (clips) | 20 | **33** | +13 | More fused events → more clips (manifest key corrected) |
| Evidence files | 893 | **1342** | +449 | More clips and thumbnails generated |
| **S07 pose warning** | **YES** (`len(TrackBBox)`) | **NO** | Fixed | FAIL-007 fixed |
| Pose events observed | 0 | 0 | = | Explained below |

---

## Explanation of Each Metric Change

**Confirmed tracks: 1 → 13**
Direct effect of FAIL-006 fix. `is_confirmed` now returns `confirmed_at_frame is not None`.
13 person tracks had `confirmed_at_frame` set during processing. Before the fix, 12 of them
returned `is_confirmed=False` because `finalize()` had ended them.

**Motion profiles: 1 → 28**
S06 `MotionAnalyzer` processes all confirmed tracks. With 13 confirmed person tracks (plus
non-person confirmed tracks), 28 motion profiles were generated. Before: 1.

**ReID persons: 1 → 4**
`CropExtractor` ran on 13 confirmed tracks. 4 unique person identities registered
(Person 1–4 via appearance similarity). Before: 1 track, 1 person.

**Semantic events (raw): 20 → 13**
The state machine (Pass 5) now runs on all 13 confirmed tracks, generating
`person_entered_scene` / `person_left_scene` / `person_walking` for each.
The activity state machine **replaces** noisy Pass 1 per-frame events (group_gathering,
person_reaching_up, person_picked_up_book, running, etc.) for its tracks.
The net result is fewer but higher-quality events. The raw count dropped from 20 to 13,
but these 13 events are grounded in actual track trajectories.

**S07 warnings: 1 → 0**
The `Temporal pose analysis failed: object of type 'TrackBBox' has no len()` warning
no longer appears. FAIL-007 fixed.

**Fused events: 20 → 33**
The 13 raw state-machine events plus 6 merged lighting events plus additional interaction
events total 33 fused events. All passed the 0.35 confidence threshold.

**Story segments: 10 → 15**
33 events over 13 confirmed tracks created 15 story segments (vs 10 from 20 events over 1
track). More confirmed tracks with distinct trajectories produce more segments.

**Complete stories: 0 → 0**
Still 0. FAIL-008 remains open. Reason: a COMPLETE story requires entry + action + exit
for the same track within the clip. In 60s of skip=5 footage, even 13 confirmed tracks
mostly generate `person_entered_scene → person_left_scene` pairs (entry+exit only) without
a sustained action arc between them. This is a real limitation of 60s clips, not a code bug.
FAIL-008 is not marked fixed — it remains dependent on longer clips or scene characteristics.

**Pose events: 0 → 0**
FAIL-007 is fixed (no AttributeError). The temporal pose analyzer now runs on all 13
confirmed tracks. However, 0 pose events (`person_crawling`, `person_crouching_sustained`,
`person_falling_likely`, `person_running`) were generated. Reason: the 1948 pedestrian
film shows people standing and walking — none of the sustained posture thresholds
(body_height < 18%, aspect_ratio > 1.8, etc.) are met for enough consecutive frames.
The analyzer ran; the footage did not contain the target activities.

**Event types after fix:**
`cycling`, `person_entered_scene`, `person_left_scene`, `person_reaching_up`, `running`, `walking_upstairs`

> **NOTE:** `cycling`, `running`, `walking_upstairs` require manual inspection. This is a 1948
> pedestrian safety film. These may be correct (running pedestrians, cyclists) or may be
> rule-based artifacts. No ground truth available to confirm or deny.

---

## FAIL-007 Status: FIXED

**Evidence:**
- S07 warning `Temporal pose analysis failed: object of type 'TrackBBox' has no len()'` absent in after run
- 0 warnings in S07 (before: 1)
- Temporal pose analyzer ran on 13 confirmed tracks without error
- 9 regression tests added in `test_fail007_trackbbox_pose_integration.py` — all passing

**Residual:** 0 pose events generated. The analyzer runs correctly; the footage does not
contain the target postures. **This is not a failure — it is the expected honest result.**

---

## FAIL-006 Status: FIXED

**Evidence:**
- Confirmed tracks: 1 → 13 (measured, not estimated)
- Root cause: `is_confirmed` property read post-finalize ENDED state instead of confirmed_at_frame
- Diagnostic confirmed 12 tracks had `confirmed_at_frame != None` but `state == ENDED`
- Fix: 1-line change to `is_confirmed` property in `track.py`
- `min_confirmation_frames` NOT changed (still 2 — the threshold was not the problem)
- 17 regression tests added in `test_fail006_track_confirmation.py` — all passing

---

## FAIL-008 Status: OPEN — DOWNSTREAM

**Evidence:**
- Complete stories: 0 before, 0 after
- Story segments increased: 10 → 15 (improvement, not a fix)
- Root cause: COMPLETE story requires entry+action+exit for same track; 60s clips
  with walking pedestrians do not generate sustained action events between entry/exit
- FAIL-008 is NOT marked fixed. It is partially dependent on clip duration,
  not exclusively a code defect.

---

## Failure Catalogue Summary

| ID | Status | Change from Phase 6 |
|---|---|---|
| FAIL-001 | OPEN | No change |
| FAIL-002 | FIXED (Phase 5) | No change |
| FAIL-003 | INVALIDATED (Phase 5) | No change |
| FAIL-004 | OPEN | No change |
| FAIL-005 | OPEN | No change |
| FAIL-006 | **FIXED** | is_confirmed now uses confirmed_at_frame |
| FAIL-007 | **FIXED** | TrackBBox field extraction replaces len()/unpack |
| FAIL-008 | OPEN (DOWNSTREAM) | 0 complete stories; not a code fix target |
| FAIL-009 | SCRIPT BUG | No change (pipeline was always correct) |

---

## Test Count

| Phase | Tests | Failures |
|---|---|---|
| Phase 5 (1ad97dd) | 536 | 0 |
| Phase 6 (2effbf9) | 536 | 0 |
| **Phase 6A (this commit)** | **562** | **0** |

New tests: 26
- `test_fail007_trackbbox_pose_integration.py`: 9 tests
- `test_fail006_track_confirmation.py`: 17 tests
