# Cycling Visual Audit — archive_001, 300 seconds, Phase 6D.1

**Purpose:** Visual inspection of 5 representative cycling events from Phase 6D/6B 300-second run  
**Date:** 2026-09-06  
**Source frames:** `PHASE6-ARCHIVE_001-300S-12F00C` evidence directory  
**Inspected:** before/event/after frames (frame_ref−1, frame_ref, frame_ref+1) for each track  
**No pipeline code modified. No thresholds changed. Read-only inspection.**

---

## Audit Results

### Track 1 — Timestamp 00:01 — conf=0.870 — mean_speed=0.0347

**Frames inspected:** 33, 34, 35

````carousel
![Track 1 — frame 33 (before)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000033.jpg)
<!-- slide -->
![Track 1 — frame 34 (event frame)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000034.jpg)
<!-- slide -->
![Track 1 — frame 35 (after)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000035.jpg)
````

**Classification: NOT_CYCLING**

All three frames show the film's animated title card: *"When YOU are a Pedestrian"*. A graphical silhouette of a traffic officer and animated child figures on a stylised background. This is the film's opening title sequence — no real persons, no bicycle. YOLO detected the animated silhouettes as persons; the silhouettes moving across the card satisfy Signal 2 (velocity ≥ 0.018 + stable height). This is detection noise from animated graphics, not a cyclist.

---

### Track 62 — Timestamp 00:55 — conf=0.725 — mean_speed=0.507

**Frames inspected:** 349, 350, 351

````carousel
![Track 62 — frame 349 (before)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000349.jpg)
<!-- slide -->
![Track 62 — frame 350 (event frame)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000350.jpg)
<!-- slide -->
![Track 62 — frame 351 (after)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000351.jpg)
````

**Classification: NOT_CYCLING**

Indoor hospital scene. A doctor and nurse are attending to a patient lying in a bed. The nurse is leaning over the patient, making sweeping arm movements. The high mean_speed (0.507 normalized/s) is caused by the nurse's arm swinging across the camera frame — not locomotion. This is one of the highest mean_speeds in the sample, fired entirely by limb movement while stationary. No bicycle present. Indoors. Definitively not cycling.

---

### Track 234 — Timestamp 02:41 — conf=0.813 — mean_speed=0.402

**Frames inspected:** 986, 987, 988

````carousel
![Track 234 — frame 986 (before)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000986.jpg)
<!-- slide -->
![Track 234 — frame 987 (event frame)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000987.jpg)
<!-- slide -->
![Track 234 — frame 988 (after)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00000988.jpg)
````

**Classification: NOT_CYCLING**

Outdoor pedestrian scene. A single man in a long overcoat is walking on a wide sidewalk beside a stone building. All three frames show him mid-stride in normal upright walking posture — both feet clearly on the ground in alternating steps. No bicycle visible anywhere in the frame. This is straightforward pedestrian walking misclassified as cycling. Signal 2 fires because walking pace at 320×240 resolution exceeds the 0.018 normalized/s threshold.

---

### Track 285 — Timestamp 03:53 — conf=0.731 — mean_speed=0.217

**Frames inspected:** 1403, 1404, 1405

````carousel
![Track 285 — frame 1403 (before)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00001403.jpg)
<!-- slide -->
![Track 285 — frame 1404 (event frame)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00001404.jpg)
<!-- slide -->
![Track 285 — frame 1405 (after)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00001405.jpg)
````

**Classification: NOT_CYCLING**

Outdoor city street intersection. Multiple pedestrians in coats and hats are crossing a wide street. A tram or bus is visible in the upper-left corner. All visible subjects are clearly walking upright on foot. The figures are small in frame (typical of overhead/distant street-level footage). No bicycle or cyclist visible in any of the three frames. This is a classic 1948 pedestrian street-crossing scene — exactly the subject matter this film was designed to depict. Signal 2 fires on walking pace.

---

### Track 532 — Timestamp 04:52 — conf=0.786 — mean_speed=0.046

**Frames inspected:** 1765, 1766, 1767

````carousel
![Track 532 — frame 1765 (before)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00001765.jpg)
<!-- slide -->
![Track 532 — frame 1766 (event frame)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00001766.jpg)
<!-- slide -->
![Track 532 — frame 1767 (after)](/C:/Users/dhruv/.gemini/antigravity/brain/8cab02bd-3943-43f1-9edd-f27fb54d5ae3/frame_00001767.jpg)
````

**Classification: NOT_CYCLING**

Outdoor residential/suburban street scene. Multiple children and an adult are moving near a 1940s automobile parked at a crosswalk. One child in the foreground appears to be jogging or running. Several other children and an adult are visible. No bicycle or cyclist anywhere in the sequence. This is a pedestrian safety demonstration — children near a car, illustrating traffic danger. The very low mean_speed (0.046, lowest in the sample) still exceeded the 0.018 threshold. Signal 2 fired on slow-moving children.

---

## Summary Table

| Track | Timestamp | Conf | mean_speed | Frames | Classification | What was actually visible |
|---|---|---|---|---|---|---|
| 1 | 00:01 | 0.870 | 0.035 | 33–35 | **NOT_CYCLING** | Animated title card silhouettes |
| 62 | 00:55 | 0.725 | 0.507 | 349–351 | **NOT_CYCLING** | Nurse's arm movement at hospital bedside |
| 234 | 02:41 | 0.813 | 0.402 | 986–988 | **NOT_CYCLING** | Man walking on outdoor sidewalk |
| 285 | 03:53 | 0.731 | 0.217 | 1403–1405 | **NOT_CYCLING** | Pedestrians crossing city street intersection |
| 532 | 04:52 | 0.786 | 0.046 | 1765–1767 | **NOT_CYCLING** | Children near parked car on residential street |

---

## Counts

| Classification | Count |
|---|---:|
| GENUINE_CYCLING | **0** |
| NOT_CYCLING | **5** |
| AMBIGUOUS | **0** |
| NOT_VERIFIABLE | **0** |
| **Total inspected** | **5** |

---

## Root Cause — Confirmed Visually

The visual evidence confirms the Phase 6C hypothesis: **Signal 2 of `ActivityClassifier._detect_cycling()` is over-triggering systematically.**

The 5 false-cycling events span four completely different scene types:
1. Animated graphics (title card)
2. Indoor arm movement (nurse, medical setting)
3. Outdoor walking pedestrian
4. Outdoor pedestrians crossing a street
5. Children near a car

**None involve a bicycle.** The variety of false-trigger contexts confirms the root cause is the threshold, not footage-specific edge cases:

```python
CYCLE_HORIZ_THRESHOLD = 0.018  # normalized units/second
```

At 320×240 resolution, frame_skip=5, fps=30:
- 1 extracted frame = 1/6 second = 0.167s
- 0.018 normalized/s × 320px = 5.76 pixels/second
- Per extracted frame: ≈ **1 pixel of centroid movement**

Any tracked object that moves 1 pixel per extracted frame with a stable detection box is classified as cycling. This describes virtually all tracked subjects in this footage.

**Signal 1 (bicycle proximity) is not the issue.** The confirmed bicycle track in S05 could cause false positives for nearby persons, but tracks 62 (indoors), 234 (outdoor walkway) and 532 (residential street) cannot possibly be near the same bicycle track. Signal 2 is the universal over-trigger.

> [!IMPORTANT]
> This audit does not quantify the full false-positive rate across 300s. 5/5 NOT_CYCLING from distributed samples is strong evidence of systematic failure, but is not a precision measurement.

---

## Decision

### **INVESTIGATE_CYCLING_CLASSIFIER_FIRST**

**Rationale:** 5 of 5 inspected samples are NOT_CYCLING across 4 different scene types. The classifier is attributing a false cycling label to:
- Animated graphics
- Limb movements of stationary persons
- Normal pedestrians at all walking speeds (0.046 to 0.507 mean_speed)

Running the 595-second pipeline before fixing this would produce a result where the majority of confirmed story segments are COMPLETE stories labelled `cycling` — but the action event in every one of those complete stories is a false classification. The complete stories produced in Phase 6D are structurally valid but their content label is wrong.

**Recommended next action:** Fix `CYCLE_HORIZ_THRESHOLD` calibration before Phase 6E / 595-second run. Do not run 595 seconds with the current threshold.

**Scope of fix:** Narrowly targeted at `CYCLE_HORIZ_THRESHOLD` in [`activity_classifier.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/utils/activity_classifier.py). Nothing else.

**Required evidence before changing:** This audit provides sufficient evidence — 5/5 NOT_CYCLING at frame level. A threshold change is now evidence-supported.
