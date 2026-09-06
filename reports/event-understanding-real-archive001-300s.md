# Event Understanding — Real Footage Audit
# archive_001 · 300 seconds · Phase 6B

**Run:** Phase 6B, archive_001, first 300s, YOLO11l balanced, skip=5, threshold=0.25
**Job:** `PHASE6-ARCHIVE_001-300S-12F00C`
**Date:** 2026-09-06

---

## Overview

232 events passed S08 confidence fusion (threshold=0.35). 92 were retained after S11 compression.

Event types in retained set (S11 kept, from manifest):

| Event type | S07 count | Retained (S11) | Dropped | Drop rate |
|---|---:|---:|---:|---:|
| cycling | 129 | 28 | 101 | 78% |
| person_entered_scene | 21 | 12 | 9 | 43% |
| person_left_scene | 20 | 12 | 8 | 40% |
| light_turned_on | 10 | 10 | 0 | 0% |
| light_turned_off | 8 | 8 | 0 | 0% |
| vehicle_approaching | 6 | 4 | 2 | 33% |
| vehicle_receding | 6 | 4 | 2 | 33% |
| person_crouching_sustained | 4 | 4 | 0 | 0% |
| person_sitting | 3 | 2 | 1 | 33% |
| vehicle_stationary | 3 | 1 | 2 | 67% |
| person_standing_up | 2 | 2 | 0 | 0% |
| running | 2 | 0 | 2 | 100% |
| walking_upstairs | 2 | 0 | 2 | 100% |
| walking_downstairs | 2 | 0 | 2 | 100% |
| person_reaching_up | 9 | 0 | 9 | 100% |
| group_gathering | 1 | 1 | 0 | 0% |
| person_picked_up_book | 1 | 1 | 0 | 0% |
| person_placed_handbag | 1 | 1 | 0 | 0% |
| person_fallen | 1 | 1 | 0 | 0% |
| person_crawling | 1 | 1 | 0 | 0% |

---

## Sampled Events — Manual Status

Labels used:
- **CORRECT** — event matches expected real-world activity based on available evidence
- **FALSE** — event does not match the activity; appears to be a misclassification
- **MISSED** — known activity that should have been detected but was not
- **AMBIGUOUS** — evidence is consistent with the event but cannot confirm or deny without watching
- **NOT VERIFIABLE** — no information available to assess correctness

> Ground truth: none. The following assessments are based on evidence metadata only.
> No frame-level inspection was conducted in this phase.

---

### person_entered_scene (sampled 3 of 21)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 00:01 | 1 | 0.90 | "Person 1 entered the scene from the bottom" | AMBIGUOUS |
| 00:30 | 14 | 0.90 | "Person 3 entered the scene from the left" | AMBIGUOUS |
| 00:39 | 34 | 0.90 | "Person 3 entered the scene from the left" | AMBIGUOUS |

**Notes:** Entry events have confidence 0.90 uniformly, suggesting a fixed confidence assignment. The direction metadata (bottom, left) is geometrically meaningful. Structurally sound but semantic correctness not verifiable.

---

### person_left_scene (sampled 3 of 20)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 00:13 | 1 | 0.75 | "Person 1 left the scene" | AMBIGUOUS |
| 00:33 | 19 | 0.90 | "Person 2 left the scene" | AMBIGUOUS |
| 00:38 | 14 | 0.90 | "Person 3 left the scene" | AMBIGUOUS |

**Notes:** Exit events are generated for tracks that end (ENDED state after finalize). Structurally correct.

---

### cycling (sampled 3 of 129)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 00:01 | 1 | 0.650 | "Person 1 is cycling across the scene" | NOT VERIFIABLE |
| 00:01 | 2 | 0.700 | "Person 2 is cycling across the scene" | NOT VERIFIABLE |
| 00:01 | 3 | 0.718 | "Person 1 is cycling across the scene" | NOT VERIFIABLE |

**Notes:**
- 129 events in 300 seconds = 0.43/second. Extremely high density.
- Tracks 1, 2, 3 all appear at t=00:01 — these are the earliest tracks.
- A 1948 pedestrian safety film plausibly contains cyclists, but 129 events is unexpected.
- The cycling rule likely triggers on fast lateral movement by person-class objects.
- Without watching the footage, cannot determine if these are real cyclists, fast walkers misclassified, or rule over-triggering on short tracks.
- **This is the most important event type to verify before any production use.**

---

### light_turned_on (sampled 3 of 10)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 00:06 | -1 | 0.970 | — | AMBIGUOUS |
| 00:08 | -1 | 0.753 | — | AMBIGUOUS |
| 00:13 | -1 | 0.970 | — | AMBIGUOUS |

**Notes:** Track -1 indicates a scene-level event (no specific object). Lighting events in the first 13 seconds are densely clustered. In a 1948 black-and-white film, scene cuts, exposure changes, or film splices would trigger luminance transitions. These may not correspond to physical light switching.

---

### vehicle_approaching / vehicle_receding (sampled 2 each)

| t | Track | Conf | Type | Status |
|---|---|---|---|---|
| 00:30 | 12 | 0.674 | vehicle_approaching | AMBIGUOUS |
| 00:30 | 12 | 0.674 | vehicle_receding | AMBIGUOUS |
| 01:27 | 80 | 0.736 | vehicle_approaching | AMBIGUOUS |
| 01:27 | 80 | 0.736 | vehicle_receding | AMBIGUOUS |

**Notes:** Track 12 generates both approaching AND receding simultaneously at t=00:30. This is likely a rule triggering simultaneously on both directions. Plausible for a vehicle passing the camera. A 1948 street film would have vehicles.

---

### running (both events)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 01:54 | 88 | 0.950 | "Person 5 is running" | AMBIGUOUS |
| 03:58 | 320 | 0.950 | "Person 10 is running" | AMBIGUOUS |

**Notes:** Confidence 0.95 for both. Running requires high lateral displacement. These were discarded by S11 compression (not retained). A pedestrian safety film may contain running; the evidence is geometrically consistent. **Discarded by S11 — not in final output.**

---

### walking_upstairs / walking_downstairs

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 01:56 | 103 | 0.930 | "Person 3 is walking up stairs" | AMBIGUOUS |
| 01:57 | 110 | 0.930 | "Person 5 is walking up stairs" | AMBIGUOUS |
| 03:56 | 298 | 0.880 | "Person 8 is walking down stairs" | AMBIGUOUS |
| 04:36 | 514 | 0.825 | "Person 7 is walking down stairs" | AMBIGUOUS |

**Notes:** High confidence (0.83–0.93). Staircase events require specific vertical movement pattern. These were also discarded by S11. Pedestrian safety films commonly feature staircase scenes. **Discarded by S11 — not in final output.**

---

### person_crouching_sustained (all 4 events)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 02:00 | 126 | 0.250 | "7 frames CROUCHING; body_h=16.49%; disp=0.558%/frame" | NOT VERIFIABLE |
| 04:23 | 481 | 0.475 | "12 frames CROUCHING; body_h=16.74%; disp=0.807%/frame" | NOT VERIFIABLE |
| 04:32 | 497 | 0.233 | "4 frames CROUCHING; body_h=17.08%; disp=0.469%/frame" | NOT VERIFIABLE |
| — | — | — | 4th event: similar | NOT VERIFIABLE |

**Notes:**
- These are the first real temporal pose events in the project history.
- Confidence is low (0.233–0.475) — the classifier is uncertain.
- Body height 16–17% of frame: threshold for crouching is < 18% (defined in `pose_temporal.py`).
- These could be: small/distant people, children, people genuinely bending, or people walking away from camera and appearing smaller.
- **NOT VERIFIABLE** without frame inspection. Important to watch before any production use.

---

### person_crawling (1 event)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 04:25 | 494 | 0.250 | "40 frames CRAWLING; body_h=12.84%; disp=0.746%/frame" | NOT VERIFIABLE |

**Notes:**
- 40 consecutive frames with CRAWLING posture is a substantial detection. This is not a single noisy frame.
- Track 494, starting ~t=04:25 in a 1948 pedestrian film.
- Body height 12.84% of frame (threshold < 15%).
- This could be: a person genuinely on hands and knees, a small child, a dog/animal misclassified as person, or a very distant/small person.
- Track 494 also generated a `person_fallen` event at t=00:53 (different observation window).
- **NOT VERIFIABLE**. Recommend inspecting the frame sequence for track 494.

---

### person_fallen (1 event)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 00:53 | 494 | 0.820 | — | NOT VERIFIABLE |

**Notes:** Confidence 0.820 — relatively high. This is also track 494. The fallen detection at t=00:53 uses bbox aspect ratio (width/height > 1.8 and body_height < 12%). Retained in the final output.

---

### group_gathering (1 event)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 00:00 | -1 | 0.800 | — | NOT VERIFIABLE |

**Notes:** Fires at t=00:00 on a scene-level track (-1). Group gathering requires multiple person tracks in close proximity. At t=00:00 (start of clip), initial detected people may cluster. Cannot verify.

---

### person_picked_up_book (1 event), person_placed_handbag (1 event)

| t | Track | Conf | Evidence | Status |
|---|---|---|---|---|
| 00:07 | 26 | 0.600 | — | NOT VERIFIABLE |
| 00:12 | 62 | 0.650 | — | NOT VERIFIABLE |

**Notes:** Interaction events. In a 1948 street film at 320×240, books and handbags would be difficult to detect reliably. These may be false positives from object proximity. Both retained in final output. **Suspicious — low confidence, early in clip, interaction with uncertain object tracks.**

---

## Summary: Event Audit

| Event type | Status | Concern level |
|---|---|---|
| cycling (129) | NOT VERIFIABLE | **HIGH — requires frame inspection** |
| person_entered_scene / left_scene | AMBIGUOUS | Low — structurally correct |
| light events | AMBIGUOUS | Medium — film artifacts possible |
| vehicle events | AMBIGUOUS | Low — plausible for street film |
| running (discarded) | AMBIGUOUS | Low |
| walking stairs (discarded) | AMBIGUOUS | Low |
| person_crouching_sustained | NOT VERIFIABLE | Medium — first real pose events |
| person_crawling | NOT VERIFIABLE | **High — 40-frame track; requires inspection** |
| person_fallen | NOT VERIFIABLE | Medium — confidence 0.82 |
| group_gathering | NOT VERIFIABLE | Medium |
| person_picked_up_book / handbag | NOT VERIFIABLE | Medium — possibly false |
| person_reaching_up (discarded) | NOT VERIFIABLE | Low |

---

## Recommendation

Before any production or further validation use of Phase 6B results:

1. **Watch the footage around the 5 `cycling` events at t=00:01–00:05.** If these are not cyclists, the cycling rule needs inspection.
2. **Watch frames around track 494** (person_crawling, person_fallen). This is the most unusual track in the dataset.
3. **Watch the person_crouching_sustained events** at t=02:00 and t=04:23–04:32.
4. **Watch the 2 interaction events** (book pickup, handbag placement) at t=00:07 and t=00:12.

No code changes should be made based on this audit. These are observations for the next experimental decision.
