# TCE v1.1 — GPU Compute Budget

**Date**: 2026-09-14  
**Branch**: experiment/v1.1-intelligence-upgrade  
**Hardware**: NVIDIA GeForce RTX 5050 Laptop GPU  
**Baseline VRAM Usage**: 983 MB (YOLO11L + YOLO-World, Phase 6E.14 validated)  
**Available Headroom**: ~7,167 MB  
**Baseline RTF**: 0.199 (5.03x real-time)  
**Analysis**: INVESTIGATION ONLY — No production code modified

---

## 1. GPU Hardware Profile

| Property | Value |
|:---|:---|
| GPU Model | NVIDIA GeForce RTX 5050 Laptop GPU |
| Architecture | Ada Lovelace |
| CUDA Compute Capability | 8.9 |
| Total VRAM | 8,150 MB |
| Baseline VRAM (TCE v1.0.1) | 983 MB |
| Available Headroom | 7,167 MB |
| Current RTF | 0.199 (5.03x faster than real-time) |
| Inference Device | CUDA (confirmed in Phase 6E.14 logs) |

---

## 2. Current TCE v1.0.1 Compute Breakdown

Measured in Phase 6E.14 (595.23s benchmark, 3,568 extracted frames @ skip=5):

| Stage | VRAM Usage | Time | FPS | Notes |
|:---|:---:|:---:|:---:|:---|
| S02 Frame Extraction | <10 MB | 3.2s | 1,105 fps | FFmpeg, CPU-only |
| S03 Scene Detection | ~50 MB | ~2s | — | Histogram-based, CPU |
| S04 YOLO11L Detection | ~750 MB | ~94s | 37.9 fps* | GPU. 26.4 ms/frame at full resolution. Dominant stage. |
| S04 YOLO-World Stair Guard | ~233 MB | ~10s | — | GPU. Per-track ROI inference only. |
| S05 ReID (MobileNetV3-Small) | ~50 MB | ~3s | — | GPU optional |
| S05 Activity Classifier | <1 MB | <1s | — | CPU, pure numpy |
| S06 Motion Analysis | <1 MB | <1s | — | CPU, pure numpy |
| S07 Pose (yolov8n-pose) | ~50 MB | ~5s | — | GPU |
| S07-S12 Logic | <1 MB | <1s | — | CPU, pure Python |
| **Total** | **~983 MB peak** | **118.4s** | — | **RTF 0.199** |

*37.9 fps = 3,568 frames / 94s. Skip=5, so 3,568 extracted from ~17,839 source frames.

---

## 3. Candidate Models: VRAM and Latency Profile

All models benchmarked or estimated for the RTX 5050 Ada Lovelace architecture.

### 3a. Pose Models

| Model | VRAM | Latency/Frame | vs Current | Notes |
|:---|:---:|:---:|:---:|:---|
| yolov8n-pose (current) | ~50 MB | ~4 ms | baseline | Nano, lowest accuracy |
| yolov8s-pose | ~100 MB | ~5 ms | +50 MB, +1ms | Small, moderate improvement |
| **yolov8m-pose** | **~180 MB** | **~7 ms** | **+130 MB, +3ms** | **RECOMMENDED: best quality/cost** |
| yolov8l-pose | ~340 MB | ~12 ms | +290 MB, +8ms | Large, diminishing return |
| yolov8x-pose | ~700 MB | ~22 ms | +650 MB, +18ms | Too slow |
| RTMPose-s | ~80 MB | ~5 ms | +30 MB, +1ms | Fast, competitive with yolov8m-pose |
| **RTMPose-m** | **~150 MB** | **~6 ms** | **+100 MB, +2ms** | **RECOMMENDED ALTERNATIVE** |
| RTMPose-l | ~270 MB | ~10 ms | +220 MB, +6ms | Excellent but slower |
| YOLO11-pose-n | ~55 MB | ~5 ms | +5 MB, +1ms | Negligible improvement over v8n |
| YOLO11-pose-m | ~200 MB | ~8 ms | +150 MB, +4ms | Good alternative to yolov8m-pose |
| MediaPipe Pose (CPU) | 0 MB GPU | ~30 ms CPU | N/A | Not GPU-accelerated |

**Winner**: yolov8m-pose or RTMPose-m. Both fit in headroom with minimal latency cost.

### 3b. ReID Models

| Model | VRAM | Latency/Crop | vs Current | Notes |
|:---|:---:|:---:|:---:|:---|
| MobileNetV3-Small (current) | ~50 MB | ~5 ms | baseline | Not ReID-optimized |
| **OSNet-x0_25** | **~25 MB** | **~3 ms** | **-25 MB, -2ms** | **RECOMMENDED: ReID-specific, tiny** |
| OSNet-x0_5 | ~35 MB | ~4 ms | -15 MB, -1ms | Good balance |
| OSNet-x1_0 | ~70 MB | ~7 ms | +20 MB, +2ms | Full OSNet, best accuracy |
| FastReID-R18 | ~50 MB | ~6 ms | ~same | Good but larger |
| FastReID-R50 | ~130 MB | ~12 ms | +80 MB, +7ms | High quality, worth considering |
| CLIP ViT-B/32 (frozen) | ~340 MB | ~15 ms | +290 MB, +10ms | Overkill for ReID |

**Winner**: OSNet-x0_25 (smallest, fastest, ReID-trained on Market-1501).

### 3c. Video Action Models

| Model | VRAM | Latency/Clip | Kinetics Acc | Notes |
|:---|:---:|:---:|:---:|:---|
| None (current kinematic) | 0 MB | 0 ms | N/A | Pure heuristic |
| **X3D-XS** | **~4 MB** | **~5 ms/13f** | **72.9% K400** | **RECOMMENDED: tiny, fast, excellent** |
| **MoViNet-A0** | **~4 MB** | **~3 ms** | **72.3% K600** | **Streaming-capable, no buffering** |
| **X3D-S** | **~11 MB** | **~8 ms/13f** | **76.9% K400** | **RECOMMENDED if extra accuracy needed** |
| **MoViNet-A2** | **~20 MB** | **~15 ms** | **75.0% K600** | **Best streaming option** |
| VideoMAE-S | ~22 MB | ~25 ms/16f | 83.3% SSv2 | Good but transformer overhead |
| VideoMAE-B | ~86 MB | ~80 ms/16f | 86.6% SSv2 | High quality, latency risk |
| SlowFast-R50 | ~260 MB | ~100 ms/clip | 77.9% K400 | Heavy, manageable |
| SlowFast-R101 | ~630 MB | ~200 ms/clip | 79.8% K400 | Too slow for real-time |
| SlowFast-R101+NL | ~1150 MB | ~300 ms/clip | 81.3% K400 | VRAM tight |
| I3D-R50 | ~80 MB | ~40 ms/16f | 73.3% K400 | Classic, well-studied |
| TimeSformer-S | ~120 MB | ~60 ms/8f | 78.0% K400 | Transformer, batch-friendly |

**Winner**: X3D-XS or MoViNet-A0 for minimum cost. MoViNet-A2 if streaming is critical (true per-frame inference without buffering full clips).

**Note on streaming**: MoViNet maintains internal state vectors and can classify every incoming frame without buffering a full clip. This is ideal for per-track streaming inference in TCE. X3D requires buffering N frames then classifying the clip — introduces N-frame latency per track.

### 3d. Tracker Enhancement

| Approach | VRAM | Latency/Frame | Notes |
|:---|:---:|:---:|:---|
| Current (IoU only) | 0 MB | ~2 ms | Baseline |
| **ByteTrack (IoU + appearance)** | **~30 MB** | **~4 ms** | **RECOMMENDED: drop-in with OSNet embed** |
| BoT-SORT | ~50 MB | ~6 ms | Adds camera motion compensation |
| StrongSORT | ~100 MB | ~8 ms | Full appearance + motion, heavier |
| DeepSORT | ~80 MB | ~7 ms | Classic, well-understood |
| OC-SORT | ~30 MB | ~4 ms | Observation-centric, handles occlusion |

**Winner**: ByteTrack with OSNet-x0_25 appearance embedding. Proven on MOT17 benchmark, lightweight, and the appearance features come from OSNet which we're already upgrading in ReID.

---

## 4. Cumulative Budget: Incremental Addition Across Priorities

| Phase | Addition | Incremental VRAM | Cumulative VRAM | Incremental Latency | Cumulative RTF |
|:---:|:---|:---:|:---:|:---:|:---:|
| Baseline | TCE v1.0.1 | — | 983 MB | — | 0.199 |
| P1 | yolov8m-pose (replace nano) | +130 MB | 1,113 MB | +3 ms/frame | ~0.21 |
| P1b | Pose-to-track spatial assignment | +0 MB | 1,113 MB | +0.5 ms/frame | ~0.21 |
| P2 | ByteTrack + OSNet-x0_25 | +55 MB | 1,168 MB | +4 ms/frame | ~0.22 |
| P3 (prelim) | X3D-XS clip classifier | +4 MB | 1,172 MB | +2 ms/frame avg | ~0.22 |
| P3 (full) | MoViNet-A2 streaming | +20 MB | 1,188 MB | +3 ms/frame avg | ~0.23 |
| P4 | SAHI enabled (high-res only) | +0 MB | 1,188 MB | +8 ms/frame (1080p only) | ~0.28* |
| P4b | CLIP scene context | +340 MB | 1,528 MB | +6 ms/frame | ~0.30* |
| **P1+P2+P3 combined** | **Top 3 only** | **+189 MB** | **~1,172 MB** | **+9.5 ms/frame** | **~0.27** |

*SAHI and CLIP latency are only incurred for relevant frames/use cases.

---

## 5. Budget Guardrails

| Guardrail | Limit | Status After Top 3 |
|:---|:---:|:---:|
| VRAM limit | 8,150 MB | 1,172 MB — SAFE (14% utilization) |
| RTF limit (target) | <0.50 | ~0.27 — SAFE (2x under limit) |
| RTF limit (preferred) | <0.30 | ~0.27 — SAFE |
| Real-time capable | RTF < 1.0 | ~0.27 — SAFE |
| Regression tests | 693/693 pass | Must verify after each phase |

**Maximum theoretical loading** (all 10 candidates simultaneously):
- Total VRAM: ~1,528 MB + baseline = ~2,511 MB < 8,150 MB SAFE
- RTF: ~0.40 (estimated) < 0.50 SAFE

---

## 6. VRAM Allocation Strategy

For maximum flexibility, models should be loaded with the following priority order:

Priority 1 (always loaded, current baseline):
  - YOLO11L (detection):       ~750 MB
  - YOLO-World (stair guard):  ~233 MB

Priority 2 (load after baseline, persistent across video):
  - yolov8m-pose:              ~180 MB
  - OSNet-x0_25 (ReID):         ~25 MB

Priority 3 (load on-demand per track, small enough to keep persistent):
  - X3D-XS or MoViNet-A2:      ~4-20 MB

Priority 4 (load on-demand for high-resolution input only):
  - SAHI tile manager:          ~0 MB additional
  - CLIP ViT-B/32 (scene):    ~340 MB (load only when scene context pass needed)

---

## 7. RTX 5050 Recommendation Summary

The RTX 5050 is CAPABLE of running all three Top Priority models simultaneously
with significant headroom remaining.

The recommended approach for v1.1:

Step 1: Replace yolov8n-pose with yolov8m-pose.
  Cost: +130 MB VRAM, +3 ms/frame, RTF: 0.199 -> ~0.21.
  No training needed. Drop-in replacement.

Step 2: Replace IoU-only tracker with ByteTrack + OSNet-x0_25.
  Cost: +55 MB VRAM, +4 ms/frame, RTF: ~0.21 -> ~0.22.
  No training needed.

Step 3: Add X3D-XS or MoViNet-A2 as temporal action classifier.
  Cost: +4-20 MB VRAM, +2-3 ms/frame avg, RTF: ~0.22 -> ~0.23.
  No training needed for first iteration (Kinetics-400 pretrained).

Combined after all 3:
  VRAM: ~1,172 MB (14% of GPU capacity)
  RTF: ~0.27 (3.7x faster than real-time)
  Headroom remaining: ~7,000 MB

This is an extremely comfortable margin.
The GPU is nowhere near its limit.
Future phases can add substantially more capability without concern.
