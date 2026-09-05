# Real Detection Experiment — archive_001_60s

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
| Duration | 60.0s |
| Frames | 1798 |

## Detection Results

| Metric | Value |
|---|---|
| Model | yolo11n.pt |
| Skip rate | every 5th frame |
| Frames processed | 360 |
| Total person detections | 661 |
| Frames with persons | 229 (63.6%) |
| Max simultaneous | 7 |
| Detection FPS | 42.4 |
| Processing time | 8.49s |
| RTF | 0.141x |
| VRAM delta | 42 MB |

## Quality Analysis

| Class | Count | % |
|---|---|---|
| NORMAL | 133 | 73.9% |
| LOW_LIGHT | 40 | 22.2% |
| VERY_LOW_LIGHT | 3 | 1.7% |
| UNUSABLE | 4 | 2.2% |

Avg luminance: 79.25  
Range: 16.38–128.44

## Evaluation

**Ground truth available:** False  
**Precision:** None  
**Recall:** None  
**F1:** None  

**Detection quality class:** CONSISTENT  
Persons detected in 63.6% of frames. Consistent detection.

## Capability Classification

| Capability | Status |
|---|---|
| Person detection (real footage) | **VALIDATED on this footage type** |
| GPU inference | **PROVEN** |
| Tracking | **NOT YET VALIDATED** — full pipeline not run |
| Events | **NOT YET VALIDATED** — full pipeline not run |
