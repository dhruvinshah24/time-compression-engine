# Phase 6E.1 — Camera Motion Dataflow Report

**Phase:** 6E.1  
**Baseline commit:** `c1351c6`  
**Previous experiment:** `175c8e9` (Phase 6D.5)  
**Date:** 2026-09-13  

---

## 1. Where Camera Motion Is Calculated

Camera motion detection is performed in **S06** ([`s06_motion_analyze.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/pipeline/stages/s06_motion_analyze.py)) via [`MotionAnalyzer._detect_camera_motion()`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/engines/perception/motion_analyzer/analyzer.py#L392-L422).

### Algorithm

```
For each frame F:
    Collect velocity vectors (dx, dy) for all active tracks at frame F.
    Compute cosine coherence of all velocity vectors.
    If coherence > camera_motion_coherence_threshold (default: 0.85):
        flag frame F as camera-motion-dominated.
```

**Coherence metric:** normalise all per-track velocity vectors, compute their mean unit vector. If the mean norm ≈ 1.0, all tracks are moving in the same direction = camera motion. Returns `list[int]` of flagged frame numbers.

**Requires:** `min_tracks_for_camera_motion` (default: value from config — checked at line 406 in analyzer.py) tracks with non-zero velocity in the frame.

---

## 2. Representation

**Level:** Frame-level list of integers.

```python
camera_motion_frames: list[int]  # raw frame numbers from original video
```

Stored in `context.metadata["camera_motion_frames"]` after S06.

- **NOT track-level**: no per-track flag is set.
- **NOT segment-level**: not grouped by scene segment.
- **NOT stored in MotionProfile**: the `MotionProfile` dataclass has no field for which of its observation frames are camera-motion-affected.

---

## 3. Camera Motion Confidence Representation

There is **no confidence value** associated with individual camera-motion frames. The detection is binary: a frame is either flagged or not, based on the threshold `camera_motion_coherence_threshold=0.85`.

The coherence value is computed but **not stored**. Only the boolean membership in `camera_motion_frames` is propagated.

---

## 4. Downstream Propagation

```
S06 → context.metadata["camera_motion_frames"] = list[int]
                ↓
S07 → reads camera_motion_frames at line 153
       → passes to EventUnderstandingEngine.understand() (Pass 1)
       → used in ActivityClassifier path? NO (see §6 below)
```

**The list is read by S07 but only used in Pass 1.**

---

## 5. Pass 1 — EventUnderstandingEngine Camera-Motion Guard

Located in [`engine.py`](file:///C:/Users/dhruv/.gemini/antigravity/scratch/time-compression-engine/backend/app/engines/semantic/event_understanding/engine.py#L217-L222):

```python
# Skip tracks whose observations fall entirely in camera-motion frames
if camera_frames and self.config.suppress_camera_motion_events:
    track_frames = {o.frame_number for o in track.observations}
    if track_frames and track_frames.issubset(camera_frames):
        camera_skipped += 1
        continue
```

**Exact semantics:** A track is suppressed from Pass 1 event generation if and only if **ALL** of its observations occur in camera-motion-flagged frames (`issubset`). A track with even one observation outside camera-motion frames is NOT suppressed.

**Configuration:** `suppress_camera_motion_events=True` by default. Reads `event_suppress_camera_motion` from settings (line 204–205 in S07).

**What events does it suppress?** Pass 1 generates `person_entered_scene`, `person_left_scene`, `person_walking`, `vehicle_approaching`, etc. Pass 5 (state machine) replaces many person events and is not directly affected by this guard. Pass 7 (narrative_builder) is completely unaffected.

---

## 6. ActivityClassifier — Camera Motion Access

**ActivityClassifier has NO access to camera_motion_frames.**

Execution path:
```
S05 → ActivityClassifier.classify(track, all_tracks)
```

`ActivityClassifier.classify()` signature (line 117 in activity_classifier.py):
```python
def classify(self, track, all_tracks: Optional[list] = None) -> ActivityResult:
```

No `camera_motion_frames` parameter. No access to S06 output at classification time. The classifier runs entirely on track observation geometry.

**ActivityClassifier is called in S05**, which runs BEFORE S06. Therefore camera_motion_frames are not even available when `classify()` is called.

**Execution order:**
```
S05 → Activity classification (track_activities stored in ctx.metadata)
S06 → Camera motion detection (camera_motion_frames stored in ctx.metadata)
S07 → narrative_builder (Pass 7) reads track_activities from ctx.metadata
      — computed by S05 before camera motion was known
```

This is the fundamental gap: **activity classification precedes camera motion detection**.

---

## 7. narrative_builder (Pass 7) — Camera Motion Access

**Pass 7 has NO camera motion guard whatsoever.**

Pass 7 code (S07 lines 701–756):

```python
activity_event_types = {
    "cycling", "running", "walking_upstairs", "walking_downstairs",
    "loitering", "walking",
}
narrative_events: list[Event] = []
for track in person_tracks:
    activity = track_activities.get(track.track_id)
    if activity is None:
        continue
    if activity.label not in activity_event_types:
        continue
    # ... emit event unconditionally ...
```

`camera_motion_frames` is read by S07 at line 153 but **only passed to Pass 1** (line 212). Pass 7 does not reference `camera_motion_frames` at all.

---

## 8. Why Pass 1 Can Suppress While Pass 7 Still Emits

**Three architectural reasons:**

**R1: Different stages.** ActivityClassifier runs in S05. Pass 7 reads S05 outputs (`track_activities`) in S07. Even if Pass 7 had access to `camera_motion_frames`, the camera motion detection (S06) ran after the classifications were already computed.

**R2: Different suppression objects.** Pass 1 suppresses *event rules* for camera-motion tracks. Pass 7 emits events from *pre-computed ActivityClassifier results*, not from re-running rules.

**R3: Pass 1 guard uses `issubset`** — only suppresses tracks entirely within camera-motion frames. Tracks with even one frame outside are not suppressed. This would not have helped even if Pass 7 used it, because none of the 5 audit tracks have any camera-motion frame overlap (see Phase 6E.1 failure trace).

---

## 9. Conclusion — Architectural Gap

The camera-motion guard was designed as a **frame-level suppression** for Pass 1 rule-based events. It was never extended to:

1. The ActivityClassifier (running in S05, before camera motion is known)
2. narrative_builder (Pass 7), which emits events based on S05 pre-computed results
3. Per-track partial overlap (only full-subset suppression is implemented)

**However, as established in the Phase 6E.1 failure trace, camera motion is NOT the root cause of the 5 false classifications.** The 53 camera-motion frames all occur in frames 20–145 (the first ~5 seconds of video). All 5 audit tracks occur at frames 929–7394 (30s–4min+). Camera motion overlap = 0% for all 5 tracks.

The root cause is **scene geometry and classification threshold mismatch** (detailed in failure trace report).
