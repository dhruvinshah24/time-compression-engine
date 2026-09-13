# 🧠 Time Compression Engine (TCE v1.0)

> **Research-Grade, Narrative-Preserving Video Intelligence & Compression Engine**  
> Transforms raw surveillance video into an intelligible, causally-connected event timeline and delivers structured, story-preserving video compression.

[![Python](https://img.shields.io/badge/Python-3.14-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js)](https://nextjs.org)
[![YOLO11](https://img.shields.io/badge/YOLO-11L-purple)](https://ultralytics.com)
[![YOLO-World](https://img.shields.io/badge/YOLO--World-v2-orange)](https://github.com/AILab-CVC/YOLO-World)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.7.0%2Bcu128-EE4C2C?logo=pytorch)](https://pytorch.org)
[![Tests](https://img.shields.io/badge/Tests-693%20passed-brightgreen)](tests/)
[![Release](https://img.shields.io/badge/Release-v1.0.1-blue)]()

---

## 1. Headline Benchmark Results (TCE v1.0 Audited)

The following metrics were empirically measured and audited during the final end-to-end benchmark validation on continuous real-world historical surveillance footage (`archive_001` / `WhenYouA1948_512kb.mp4`):

| Headline Metric | Measured Result | Context / Verification |
| :--- | :---: | :--- |
| **Pipeline Architecture** | **12 Stages ($S01 \to S12$)** | Fully automated end-to-end execution |
| **Footage Duration** | **595.23 Seconds (~10 Min)** | $17,839$ raw frames @ $29.97$ fps ($320 \times 240$) |
| **Total Pipeline Runtime** | **118.4 Seconds** | Complete $S01 \to S12$ processing time |
| **Real-Time Factor (RTF)** | **0.199** | **$5.03\times$ faster than real-time playback** |
| **Hardware Platform** | **NVIDIA RTX 5050 Laptop GPU** | Peak VRAM: **$983$ MB** (< 1.0 GB memory footprint) |
| **Object Detections** | **4,375 Detections** | YOLO11 Large, $26.4$ ms/frame ($2,290$ person detections) |
| **Tracking Trajectories** | **954 Total / 187 Confirmed** | ByteTrack-style Kalman tracking ($41$ unique identities post-ReID) |
| **Fused Semantic Events** | **294 Events** | Fused across $18$ domain rules ($117$ narrative events) |
| **Story Segments** | **159 Segments** | $12$ COMPLETE, $55$ PARTIAL, $1,643$ graph edges |
| **Lossy Compression Ratio** | **0.398 Achieved** | $40.0\%$ target compression ratio budget |
| **Story Preservation** | **12 / 12 Intact (100%)** | **$100.0\%$ chain atomicity** preserved across complete stories |
| **Exported Artifacts** | **4,327 Artifact Files** | $117$ MP4 clips, $117$ event thumbnails, $4,188$ preview frames |
| **False Stair Suppression**| **69 / 69 Suppressed (100%)** | $100.0\%$ false positive rejection on archive footage |
| **Holdout Stair Recall** | **25 / 25 Detected (100%)** | $100.0\%$ precision and recall on independent 50-item benchmark |
| **Regression Test Suite** | **693 / 693 Passed (100%)** | $0$ failures, $0$ regressions in $16.85$s |

---

## 2. System Architecture & Central Idea

### The Central Idea: Story-Preserving Compression
Traditional video compressors (H.264, H.265) operate at the pixel block level, discarding high-frequency visual details to save bandwidth. Conventional video summarizers sample isolated high-motion frames or motion bursts, producing disjointed clips that discard human context.

**TCE treats surveillance video as a causal narrative.** Instead of simply selecting the most active frames, TCE structures video into an **event graph** and enforces **narrative chain atomicity**:
$$\text{PERSON ENTERS} \longrightarrow \text{ACTION (walking, running, cycling, interaction)} \longrightarrow \text{PERSON EXITS}$$
Under lossy budget compression (e.g., $40\%$ target duration), complete narrative chains are preserved as indivisible narrative units rather than fractured into uninterpretable fragments.

```
[Raw Surveillance Video]
   │
   ▼  PERCEPTION INTELLIGENCE ENGINE (S01–S06)
   ├─ S01 Ingestion & Upload       -> Metadata probe, resolution, initial preview
   ├─ S02 Frame Extraction         -> Chunked extraction, configurable skip (5x = 6 fps)
   ├─ S03 Scene Detection          -> Histogram boundary detection, keyframe selection
   ├─ S04 Object Detection         -> Ultralytics YOLO11 Large, CLAHE quality assessment
   ├─ S05 Multi-Object Tracking    -> ByteTrack / Kalman filter, ReID appearance matching
   ├─ S06 Motion Analysis          -> Centroid velocity, optical flow homography camera compensation
   │
   ▼  SEMANTIC INTELLIGENCE ENGINE (S07–S08)
   ├─ S07 Event Understanding      -> 18 rule definitions, temporal state machines, pose gestures,
   │                                  SceneStairGuard (YOLO-World v2 on dynamic 1.5x Person ROIs)
   ├─ S08 Confidence Fusion        -> Weighted linear multi-source confidence fusion (detection, motion, rule, tracking, scene)
   │
   ▼  TEMPORAL INTELLIGENCE ENGINE (S09–S12)
   ├─ S09 Story Building           -> Directed Event Graph G=(V,E), story completeness state machine
   ├─ S10 Narrative Ranking        -> Multi-factor importance & narrative scoring
   ├─ S11 Summarization Policy     -> Target duration budgeting with Narrative Chain Atomicity
   └─ S12 Export & Packaging       -> FFmpeg clip slicing, thumbnail generation, sequence validation
```

---

## 3. Validation

### The 595.23-Second Benchmark
The system was validated on the complete, continuous 595.23-second video `WhenYouA1948_512kb.mp4` ($17,839$ frames, historical Oakland street surveillance):
- **Full End-to-End Stability**: All 12 stages executed sequentially with **0 exceptions, 0 pipeline crashes, and 0 missing output files**.
- **Real-Time Factor (RTF)**: **0.199** ($118.4$ seconds total runtime, processing at $5.03\times$ real-time speed).
- **GPU Resource Footprint**: Peak VRAM was **983 MB** on a mobile NVIDIA GeForce RTX 5050 GPU.
- **Narrative Completeness**: Successfully assembled and exported **12 structurally COMPLETE story chains** (up from 1 in baseline configurations).

> [!NOTE]
> **Validation Boundary Disclaimer:**  
> This validates the end-to-end pipeline, throughput, story preservation, and perspective compensation on the tested benchmark. **It does not establish universal CCTV accuracy across all unconstrained camera angles, environments, or lighting conditions.**

---

## 4. What Has Been Validated

To maintain strict scientific honesty, capabilities are explicitly divided into three categories:

### 4.1 Empirically Validated
- **Sub-Real-Time Throughput**: Consistently achieves $\text{RTF} < 0.20$ on consumer GPU hardware.
- **Continuous 10-Minute Pipeline Execution**: 595.23 seconds processed without memory leaks or degradation.
- **Perspective False Stair Elimination**: $100.0\%$ of perspective-induced false stair triggers rejected ($69/69$ on archive footage).
- **Holdout Stair Recognition**: $100.0\%$ precision ($25/25$) and recall ($25/25$) on an independent 50-item benchmark.
- **Lossy Narrative Preservation**: $100.0\%$ of complete story chains ($12/12$) preserved intact under $40\%$ compression.
- **Camera-Motion Compensation**: Homography-based optical flow flagged 77 jitter frames, cleanly suppressing 3 false perspective tracks.
- **Artifact Export**: 4,327 files (117 MP4 clips, 117 event thumbnails, 4,188 preview frames) verified on disk.

### 4.2 Implemented & Exercised (Unlabelled Ground Truth)
- **Pose Gestures & Postures** (`person_reaching_up`, `person_crouching_sustained`, `person_sitting`, `person_standing_up`, `person_fallen`): Implemented and verified to trigger events in the output timeline, but unlabelled against dense ground-truth bounding boxes on archive footage.
- **Multi-Person Interactions** (`group_gathering`, `group_dispersing`): Evaluated by spatial proximity rules, but precision/recall is unquantified against ground truth.
- **Low-Light CLAHE Enhancement**: Implemented in S04 and exercised on synthetic low-light tests, but bypassed on daylight archive footage.
- **Adaptive Frame Skip**: Implemented in S02 and tested in unit suites, while reference benchmarks utilized fixed frame skip ($5\times$).

### 4.3 Future Validation
- **24-Hour Continuous Streaming**: Longest validated continuous video is 595.23 seconds (~10 minutes).
- **Multi-Camera Pedestrian Hand-off**: Cross-camera re-identification is not implemented.
- **Modern 4K / 1080p RTSP Stream Generalization**: Benchmarks utilized 320x240 monochrome archive video.
- **Universal Action Recognition**: No overall "95% action accuracy" is manufactured; action recognition is heuristic-driven.

---

## 5. Case Study: The Perspective Stair Problem

### The Challenge
In 2D surveillance video, vertical centroid velocity ($\\Delta y / \\Delta t$) cannot distinguish physical elevation change from perspective depth motion (a pedestrian walking toward or away from a tilted camera). In Phase 6D, this caused **79 false stair climbing events** to leak into a 300-second timeline.

### Investigated and Refuted Hypotheses
1. **Posture Gating (Phase 6E.4)**: Hypothesized that bounding box normalized height variance would distinguish stair stepping from walking. **Empirically refuted**: median variance on flat walking ($0.1017$) was indistinguishable from stairs ($0.1076$).
2. **Hard Binary Scene Guard (Phase 6E.7)**: Hypothesized that a strict binary scene confidence cutoff ($c_{scene} \ge 0.20$) would guard against false triggers. **Empirically refuted**: destroyed positive stair recall ($0/7$ real stairs retained).

### The Validated Solution: Multi-Scale Scene Perception Guard
Implemented in `backend/app/utils/scene_stair_guard.py` and Stage S07:
1. **Automatic 1.5x Person ROI**: Expands track bounding boxes by $1.5\times$ without manual coordinates.
2. **Open-Vocabulary Scene Detection**: YOLO-World evaluates an expanded 12-prompt staircase vocabulary on the local ROI.
3. **Spatial & Temporal Gating**: Gated by Intersection-over-Person ($\text{IoP} \ge 0.15$) and temporal persistence ($p \ge 2$).
4. **Multiplicative Soft Evidence Model**:
   $$\text{QualityScore} = \min\left(1.0, \frac{c_{scene}}{0.05} \cdot \frac{p_{scene}}{5.0} \cdot \min\left(1.0, \frac{\text{IoP}}{0.20}\right)\right)$$
   $$c_{stair} = c_{vel} \cdot (0.30 + 0.70 \cdot \text{QualityScore})$$

### Empirical Results:
- **Independent Holdout Benchmark (50 unseen sequences)**: $25/25$ stairs detected ($100\%$ recall), $0/25$ false alarms ($100\%$ precision), F1 = 1.000.
- **595s Archive Footage**: **69 of 69 candidate stair triggers suppressed ($100.0\%$ suppression, 0 leaked)**.

---

## 6. Compression Integrity & Validator Audit

In Stage S12, the pipeline includes a structural sequence validator (`sequence_validator.py`). During the 595s run, S12 recorded 12 minor warnings:
`[NARRATIVE ERROR] complete_chain_integrity: Segment <id> was COMPLETE but after compression is missing: action`

A dedicated audit (commit `4f74f37`) verified the exact empirical cause:
- **Zero Story Breaks**: In all 12 complete story chains, **100.0% of the constituent events (entry, action, exit) were preserved and exported**.
- **Root Cause**: `SequenceValidator._ACTION_EVENTS` was desynchronized from `StoryBuilder._ACTION_EVENTS` (which was updated in Phase 6D.4 to include `'running'` and `'cycling'`). The validator was looking for `'person_running'` and generated a false alarm.
- All 117 video clips and 4,188 thumbnails exist on disk with zero missing files.

---

## 7. Key Technical Contributions

1. **Narrative-Preserving Lossy Compression**: Enforces graph-based chain atomicity ($ENTRY \to ACTION \to EXIT$) under lossy budget constraints.
2. **Context-Gated Kinematic Elevation Reasoning**: Resolves perspective depth motion vs. true physical climbing by localizing open-vocabulary scene perception to dynamic $1.5\times$ person ROIs.
3. **Multi-Signal Confidence Fusion**: Replaces brittle single-detector thresholds with weighted linear fusion across detection, velocity, domain rules, track stability, and scene reliability.
4. **Structured Decision Explainability**: Every semantic event decision attaches a verifiable evidence chain recording individual signal scores, weights, spatial relations, and fallback paths.
5. **Disciplined Failure-Driven Engineering**: Formally refuted false hypotheses and validated fixes on independent holdout sets before production integration.

---

## 8. Limitations

- **10-Minute Maximum Validated Window**: 24-hour continuous surveillance streaming is not validated.
- **Single-Camera Scope**: Multi-camera pedestrian hand-off across non-overlapping views is not implemented.
- **Resolution Generalization**: Evaluated on historical 320x240 monochrome video; modern 4K/1080p RTSP camera streams remain future work.
- **Heuristic Action Scope**: Action recognition relies on bounding box kinematics and heuristics rather than heavy end-to-end action transformers.

---

## 9. Quick Start & Demonstration

### Prerequisites
- Python 3.11+ (tested on Python 3.14)
- Node.js 18+
- NVIDIA GPU with CUDA support (CPU fallback supported)

### 1. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open **http://localhost:3000** in your browser.

### 3. Demonstration Workflow
1. Navigate to **Upload** (`/upload`).
2. Select a surveillance video and choose a processing profile (`balanced` recommended).
3. Click **Start Processing** and monitor live progress through stages $S01 \to S12$ on `/processing/[jobId]`.
4. Open the **Timeline** (`/timeline/[videoId]`) to inspect detected events, confidence badges, and play generated MP4 highlight clips.
5. Open the **Diagnostics Panel** to view extraction speeds, detection distributions, and export statistics.

---

## 10. Documentation Index

- **Final Assessment**: [`reports/TCE-v1.0-final-assessment.md`](reports/TCE-v1.0-final-assessment.md)
- **Release Checklist**: [`docs/TCE-v1.0-release-checklist.md`](docs/TCE-v1.0-release-checklist.md)
- **595s Benchmark Report**: [`reports/phase-6-e-14-595s-validation.md`](reports/phase-6-e-14-595s-validation.md)
- **Compression Audit Report**: [`reports/phase-6-e-14-compression-warning-audit.md`](reports/phase-6-e-14-compression-warning-audit.md)
- **Architecture Specification**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Engine Reference**: [`docs/ENGINES.md`](docs/ENGINES.md)
- **Research Contributions**: [`docs/RESEARCH_CONTRIBUTIONS.md`](docs/RESEARCH_CONTRIBUTIONS.md)

---

**Dhruvin Shah** — [@dhruvinshah24](https://github.com/dhruvinshah24)