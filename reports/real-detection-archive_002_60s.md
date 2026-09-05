# Real Detection Experiment — archive_002_60s

Measured: 2026-09-05 23:02  
Git commit: b654937  

> Values are **measured from real footage**, not synthetic.

## Hardware

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 5050 Laptop GPU |
| GPU available | True |
| VRAM total | 8151 MB |
| PyTorch | 2.13.0+cu132 |
| CUDA | 13.2 |

## Video

| Item | Value |
|---|---|
| Resolution | 640x360 |
| FPS | 23.98 |
| Duration | 60.0s |
| Frames | 1438 |

## Detection Results

| Metric | Value |
|---|---|
| Model | yolo11n.pt |
| Skip rate | every 5th frame |
| Frames processed | 288 |
| Total person detections | 75 |
| Frames with persons | 65 (22.6%) |
| Max simultaneous | 2 |
| Detection FPS | 77.6 |
| Processing time | 3.71s |
| RTF | 0.062x |
| VRAM delta | 10 MB |

## Quality Analysis

| Class | Count | % |
|---|---|---|
| NORMAL | 66 | 45.8% |
| LOW_LIGHT | 55 | 38.2% |
| VERY_LOW_LIGHT | 8 | 5.6% |
| UNUSABLE | 15 | 10.4% |

Avg luminance: 54.09  
Range: 0.88–117.74

## Evaluation

**Ground truth available:** False  
**Precision:** None  
**Recall:** None  
**F1:** None  

**Detection quality class:** PARTIAL  
Persons detected in 22.6% of frames. Moderate detection rate.

## Capability Classification

| Capability | Status |
|---|---|
| Person detection (real footage) | **PARTIALLY VALIDATED** |
| GPU inference | **PROVEN** |
| Tracking | **NOT YET VALIDATED** — full pipeline not run |
| Events | **NOT YET VALIDATED** — full pipeline not run |
