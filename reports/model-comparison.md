# Model Comparison — TCE v1.0.1

Measured: 2026-08-26 17:42  
Device: NVIDIA GeForce RTX 5050 Laptop GPU  
Benchmark: 100 frames @ 1080p  

> **Note:** FPS values are measured. Detection counts are on synthetic video.
> Detection precision/recall require real annotated footage (NOT YET AVAILABLE).

## Measured FPS

| Model | FPS (measured) | ms/frame | VRAM load (MB) | VRAM inference (MB) | Status |
|---|---|---|---|---|---|
| yolo11n.pt | 38.14 | 26.22 | 30 | 90 | MEASURED |
| yolo11s.pt | 36.72 | 27.23 | 82 | 150 | MEASURED |
| yolo11m.pt | 30.08 | 33.25 | 130 | 268 | MEASURED |
| yolo11l.pt | 21.66 | 46.16 | 234 | 366 | MEASURED |
| yolo11x.pt | 21.86 | 45.75 | 380 | 536 | MEASURED |

## Detection Counts (Synthetic Video)

| Model | Total Detections | Avg/Frame | Classes Detected |
|---|---|---|---|
| yolo11n.pt | 0 | 0.0 | none |
| yolo11s.pt | 0 | 0.0 | none |
| yolo11m.pt | 23 | 0.23 | tv:23 |
| yolo11l.pt | 0 | 0.0 | none |
| yolo11x.pt | 0 | 0.0 | none |

## Notes

- Detection counts on synthetic videos are **expected to be near zero**.
  YOLO11 models are trained on COCO, not on geometric shapes.
- FPS measurements are **reliable** and hardware-dependent.
- VRAM values reflect PyTorch reserved memory, not CUDA total.
- Precision / Recall / mAP: **NOT MEASURED** — requires annotated real footage.

## Capability Classification

| Capability | Classification |
|---|---|
| FPS per model | **PROVEN** (measured this run) |
| VRAM per model | **PROVEN** (measured this run) |
| Detection accuracy on real people | **NOT YET VALIDATED** — no annotated footage |
| Best model choice | **INCONCLUSIVE** — cannot determine without real footage |
