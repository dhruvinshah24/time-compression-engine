# Algorithm Documentation — Time Compression Engine

This document records every algorithm implemented in the system with full rationale.
By the end of the project, this document constitutes the **methodology chapter** of the research report.

Each entry answers three questions:
1. **Why was this algorithm chosen?**
2. **How do we know it works?** (test coverage + benchmark results)
3. **Is it better than the alternative?** (comparison against baselines)

---

## Table of Contents

- [Phase 2: Frame Extraction — Deterministic Stride Sampling](#phase-2-frame-extraction)
- [Phase 3A: Scene Change Detection — Adaptive Histogram Difference](#phase-3a-scene-change-detection)
- [Phase 3B: Object Detection — YOLOv8n via Model Registry](#phase-3b-object-detection)
- [Phase 4: Multi-Object Tracking — IoU Hungarian Matching](#phase-4-multi-object-tracking)
- [Phase 5: Motion Analysis — Centroid Velocity Estimation](#phase-5-motion-analysis)
- [Phase 7: Confidence Fusion (planned)](#phase-7-confidence-fusion-planned)
- [Phase 8: Story Preservation (planned)](#phase-8-story-preservation-planned)
- [Phase 9: Compression Policy (planned)](#phase-9-compression-policy-planned)

---

## Phase 2: Frame Extraction

### Algorithm: Deterministic Stride Sampling

**Problem:** Extract a representative subset of frames from a video for downstream analysis without processing every frame.

**Inputs:** Full video file (any supported format), frame skip rate N.

**Outputs:** Set of JPEG frames, one per every N original frames.

**Implementation:** `utils/ffmpeg.py → extract_frames()`
**Stage:** `pipeline/stages/s02_extract.py`

**Method:**
```
FFmpeg filter: select='not(mod(n, N))', setpts=N/FRAME_RATE/TB
```
Select every N-th frame using the original frame index (not resampled timestamps).

**Complexity:** O(total_frames / N) for extraction; O(1) memory per frame.

**Why this approach over alternatives:**

| Approach | Problem |
|---|---|
| `-r {fps}` resampling | Interpolates frames — introduces duplicates not in original. Non-deterministic for VFR. |
| PyAV frame iteration | Python overhead per frame. 10x slower for 24-hour videos. |
| Uniform random sampling | Not reproducible without a fixed seed. Breaks benchmark comparison. |
| **Stride sampling (chosen)** | Deterministic, fast (C-level FFmpeg), no frame interpolation, VFR-safe. |

**Determinism guarantee:** `select=not(mod(n, N))` uses frame index `n`, which is purely a function of the input video. Given identical input + identical N → identical output frames, always.

**Limitations:**
- If a meaningful event occurs entirely within a skipped window, it will be missed.
- Mitigated in Phase 3A: scene change detection inserts keyframes at detected boundaries.
- Future: adaptive skip rate that densifies around detected change points.

**Benchmark results:** *(fill after running benchmark suite)*

---

## Phase 3A: Scene Change Detection

### Algorithm: Adaptive Histogram Difference with Pixel Fallback

**Problem:** Given a sequence of video frames, identify frame boundaries where the visual content meaningfully changes — distinguishing real scene transitions from noise, lighting variation, and camera shake.

**Inputs:** Ordered list of extracted frame images (JPEG paths + frame numbers).

**Outputs:**
- Per-frame `FrameScore` (pixel_diff, histogram_diff, composite, adaptive_threshold, decision_reason)
- `SceneSegment` list — contiguous video segments between boundaries
- Final keyframe list

**Implementation:** `engines/perception/change_detector/`
**Stage:** `pipeline/stages/s03_scene_detect.py`

**Method (two-signal composite):**

**Signal 1 — Normalized Pixel Difference:**
```
gray_t  = grayscale(frame_t)
gray_{t-1} = grayscale(frame_{t-1})
pixel_diff = mean(|gray_t - gray_{t-1}|) / 255
```
Range [0.0, 1.0]. Fast. Sensitive to all pixel-level changes including noise.

**Signal 2 — HSV Histogram Correlation:**
```
hist_t = histogram(HSV(frame_t), bins=16 per channel)
hist_diff = 1.0 - pearson_correlation(hist_t, hist_{t-1})
```
Range [0.0, 1.0]. Robust to local pixel noise — captures global color distribution shift.

**Composite Score:**
```
composite = (pixel_weight × pixel_diff) + (histogram_weight × hist_diff)
```
Default weights: `pixel=0.4`, `histogram=0.6`.

**Adaptive Threshold:**
```
threshold(t) = mean(composite[t-W : t]) + k × std(composite[t-W : t])
```
Rolling window W=50 frames, k=1.5. Adapts to each video's noise floor in real time.

**Classification Rules:**
1. `composite > hard_cut_threshold (0.7)` → **hard_cut**
2. `composite > adaptive_threshold(t)` → **scene_boundary**
3. `composite < duplicate_threshold (0.02)` → **duplicate**
4. Otherwise → **normal frame**

**Explainability:** Every frame stores a `decision_reason` field — e.g. `"hard_cut: composite=0.82 > threshold=0.70"`. This is the foundation of the explainability objective.

**Complexity:**
- Time: O(n) — single pass
- Space: O(W) — rolling window only

**Why this approach over alternatives:**

| Approach | Tradeoff |
|---|---|
| SSIM (Structural Similarity) | O(W×H×11²) convolution per frame. Designed for perceptual quality assessment, not scene change detection. Higher computational cost is not justified for a preprocessing stage. |
| Optical Flow (Lucas-Kanade) | Designed for motion estimation. Dense flow is O(W×H×iterations). Provides motion vectors, not scene boundaries directly. |
| Perceptual Hash (pHash) | Loses color information. Poor sensitivity to lighting-change events. |
| Simple frame diff only | Single spatial signal — high false positive rate on noisy or shaky cameras. |
| **Histogram + Pixel composite (chosen)** | Two independent signals. O(n) time. Interpretable threshold. |

> **Note on SSIM comparison:** The pixel-plus-histogram approach was chosen because it provides lower computational cost and sufficient accuracy for long-duration video preprocessing. SSIM remains a strong alternative where perceptual similarity is the primary objective. The claim is not universal superiority, but suitability to these specific constraints (24-hour video, bounded memory, O(n) requirement).

**Limitations:**
- Slow fade transitions may score below threshold.
- Global lighting-only changes (e.g., lights-on) can trigger false boundary — mitigated by `lights_changed` event type in knowledge base.

**Benchmark results:** *(fill after running Phase 3A benchmark suite)*

---

## Phase 3B: Object Detection

### Algorithm: Single-Stage Detection via YOLOv8n + Model Registry Abstraction

**Problem:** Detect and classify objects (person, vehicle, parcel) in each keyframe produced by Phase 3A.

**Implementation:** `engines/perception/object_detector/` + `model_registry/`
**Stage:** `pipeline/stages/s04_object_detect.py`

**Method:** YOLOv8n — single forward pass per image yields class labels, confidence scores, and bounding boxes. Internal NMS removes duplicate detections. Output normalized to [0, 1] for resolution-independence.

**Model Registry abstraction:** The pipeline never calls YOLO directly. `BaseDetectionModel.detect()` is the only interface downstream code uses. Swapping to RT-DETR requires zero pipeline changes.

**Phase 3B configuration:** `yolov8n`, confidence=0.72, COCO subset (person, car, truck, bus, bicycle, backpack, handbag, suitcase, cell phone).

**Upgrade path (Phase 9):** Swap to `yolov8s` or `rtdetr-l` after evaluation metrics are established.

**NMS metrics:**
- `pre_confidence_filter_count`: raw boxes from YOLO after its internal NMS, before our threshold.
- `filtered_out_count`: further rejected by our threshold.
- Note: YOLO's pre-NMS count is not exposed by the standard API.

**Why YOLO over alternatives:**

| Approach | Tradeoff |
|---|---|
| Faster R-CNN (two-stage) | Higher accuracy. ~10× slower. Not suitable for long video. |
| SSD | Comparable speed. Lower accuracy on small objects. |
| DINO / Grounding DINO | Better open-vocabulary. Much heavier. Planned Phase 9. |
| **YOLOv8n (chosen)** | Best speed/accuracy for Phase 3B baseline. Single-stage. Actively maintained. |

**Benchmark results:** *(fill after running Phase 3B benchmark suite)*

---

## Phase 4: Multi-Object Tracking

### Algorithm: IoU-based Hungarian Matching with Track Lifecycle State Machine

**Problem:** Assign consistent identities (Track IDs) to physical objects across video frames.
"Is the person in frame 47 the same person as in frame 52?"

**Inputs:** Sequence of `FrameDetectionResult` (output of Phase 3B).
**Outputs:** `Track` objects with full observation history, lifecycle state, and motion history.

**Implementation:** `engines/perception/tracker/`
**Stage:** `pipeline/stages/s05_track.py`

**Method (4-step update loop per frame):**

**Step 1 — IoU Matrix:**
```
iou_matrix[i,j] = IoU(track_i.bbox, detection_j.bbox)
IoU = Area(Intersection) / Area(Union) ∈ [0, 1]
```

**Step 2 — Hungarian Assignment:**
```
cost_matrix = 1.0 - iou_matrix
row, col = linear_sum_assignment(cost_matrix)   # O(n³)
accept pairs where iou >= iou_threshold (0.3)
```

**Step 3 — Lifecycle transitions:**
```
Matched:   lost_frames=0; LOST→ACTIVE; TENTATIVE+N matches→ACTIVE
Unmatched: lost_frames+=1; if > max_lost → ENDED
New dets:  conf >= min → create TENTATIVE track
```

**Track lifecycle state machine:**
```
TENTATIVE → ACTIVE  (min_confirmation_frames consecutive matches)
ACTIVE    → LOST    (no match this frame)
LOST      → ACTIVE  (re-matched after occlusion)
LOST      → ENDED   (exceeded max_lost_frames)
TENTATIVE → ENDED   (no match in first frame — noise rejection)
```

**Why TENTATIVE state?** Without it, every noise detection creates a track. Requiring 2 consecutive matches before confirmation eliminates ghost tracks in low-light and rainy footage.

**Key invariant:** Same physical object always gets the same Track ID. Tested explicitly.

**Why IoU + Hungarian over alternatives:**

| Approach | Tradeoff |
|---|---|
| Centroid distance (greedy) | Fast but fails at occlusions and crossed paths. |
| Mahalanobis + Kalman (SORT) | Better occlusion handling. Phase 9 upgrade target. |
| ReID embeddings (DeepSORT) | Best re-ID. Requires CNN feature extractor. Phase 9+. |
| **IoU + Hungarian (chosen)** | Optimal assignment. O(n³) negligible for n<50. Interpretable threshold. |

**Benchmark results:** *(fill after running Phase 4 benchmark suite)*

---

## Phase 5: Motion Analysis

### Algorithm: Centroid Velocity Estimation with Motion Classification

**Problem:** For each tracked object, compute velocity, speed class, and direction from track observation history. Detect camera-induced global motion.

**Inputs:** `TrackingResult` (output of Phase 4) — tracks with full observation histories.
**Outputs:** Per-track `MotionProfile` (velocity, speed_class, direction, approach/recede signal).

**Implementation:** `engines/perception/motion_analyzer/`
**Stage:** `pipeline/stages/s06_motion_analyze.py`

**Method:**

**Velocity estimation (per consecutive observation pair):**
```
dx = center_x(t) - center_x(t-1)
dy = center_y(t) - center_y(t-1)
dt = timestamp_ms(t) - timestamp_ms(t-1)
velocity = (dx/dt, dy/dt)   # normalized coords per ms
speed = sqrt(dx² + dy²) / dt
```

**Speed classification (thresholds in normalized units/second):**
```
stationary:   speed < 0.01
slow:         0.01 <= speed < 0.05
walking:      0.05 <= speed < 0.15
fast:         speed >= 0.15
```

**Direction classification (8-compass):**
```
angle = atan2(dy, dx) → mapped to N/NE/E/SE/S/SW/W/NW
```

**Approach/Recede detection:**
```
area_t = (bbox_x2 - bbox_x1) * (bbox_y2 - bbox_y1)
if area_t > area_{t-1} * 1.05 → approaching
if area_t < area_{t-1} * 0.95 → receding
```

**Camera motion detection:**
If mean velocity of all active tracks is coherent (cosine similarity > threshold), flag as camera motion. This prevents spurious events when the camera itself moves.

**Why centroid-based over optical flow:**

| Approach | Tradeoff |
|---|---|
| Dense optical flow (Farneback) | Pixel-level vectors for every pixel. O(W×H×iterations). Too expensive for Phase 5. |
| Sparse optical flow (Lucas-Kanade) | Corner-based vectors. Requires feature extraction. High complexity for tracked objects already identified. |
| **Centroid velocity (chosen)** | Direct from Phase 4 track data. O(1) per observation pair. No additional image processing. |

> **Phase 9 upgrade:** Dense optical flow for camera motion compensation will be added when benchmark evaluation (05_camera_shake, 10_variable_fps) reveals centroid estimation is insufficient.

**Benchmark results:** *(fill after running Phase 5 benchmark suite)*

---

## Phase 7: Confidence Fusion (planned)

**Algorithm:** Weighted linear fusion with configurable signal weights
**Problem:** Combine confidence signals from all Perception Engine modules.
**Mathematical form:** $C_{fused} = \sum_{i} w_i \cdot C_i$, $\sum w_i = 1$
**Novel contribution:** Weight adaptation based on domain and lighting context.
**Notes:** *(to be documented when implemented)*

---

## Phase 8: Story Preservation (planned)

**Algorithm:** Causal chain detection via event graph traversal
**Problem:** Ensure that causally-linked event sequences are preserved together.
**Novel contribution:** Treating compression as a graph problem rather than a ranking problem.
**Notes:** *(to be documented when implemented)*

---

## Phase 9: Compression Policy (planned)

**Algorithm:** Narrative-aware subgraph selection
**Problem:** Decide which events to include in the compressed output video.
**Novel contribution:** Story-coherent compression vs. naive importance thresholding.
**Notes:** *(to be documented when implemented)*
