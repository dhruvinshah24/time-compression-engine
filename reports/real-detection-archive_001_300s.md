# Real Detection Experiment — archive_001_300s

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
| Resolution | 320x240 |
| FPS | 29.97 |
| Duration | 300.0s |
| Frames | 8991 |

## Detection Results

| Metric | Value |
|---|---|
| Model | yolo11n.pt |
| Skip rate | every 5th frame |
| Frames processed | 1799 |
| Total person detections | 3658 |
| Frames with persons | 1033 (57.4%) |
| Max simultaneous | 15 |
| Detection FPS | 73.7 |
| Processing time | 24.41s |
| RTF | 0.081x |
| VRAM delta | 10 MB |

## Quality Analysis

| Class | Count | % |
|---|---|---|
| NORMAL | 812 | 90.2% |
| LOW_LIGHT | 71 | 7.9% |
| VERY_LOW_LIGHT | 4 | 0.4% |
| UNUSABLE | 13 | 1.4% |

Avg luminance: 94.76  
Range: 10.4–187.47

## Evaluation

**Ground truth available:** False  
**Precision:** None  
**Recall:** None  
**F1:** None  

**Detection quality class:** CONSISTENT  
Persons detected in 57.4% of frames. Consistent detection.

## Capability Classification

| Capability | Status |
|---|---|
| Person detection (real footage) | **VALIDATED on this footage type** |
| GPU inference | **PROVEN** |
| Tracking | **NOT YET VALIDATED** — full pipeline not run |
| Events | **NOT YET VALIDATED** — full pipeline not run |
