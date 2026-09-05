# Model Comparison on Real Footage — Phase 5F

Clip: `WhenYouA1948_512kb.mp4` first 60s | 320x240 @ 30.0fps  
Measured: 2026-09-05 23:10  

| Model | Total Det | Frames% | MaxSim | Det FPS | RTF | VRAM +MB |
|---|---|---|---|---|---|---|
| yolo11n.pt | 661 | 63.6% | 7 | 44.5 | 0.135x | 58 |
| yolo11l.pt | 820 | 69.4% | 6 | 41.4 | 0.145x | 98 |
| yolo11x.pt | 796 | 70.3% | 6 | 32.9 | 0.183x | 222 |

## Findings

- Most detections: **yolo11l.pt**
- Most VRAM-efficient: **yolo11n.pt**
- Note: higher detection count is NOT necessarily better — may include false positives.
- Ground truth unavailable — cannot compute precision/recall/F1.

## Capability Classification

| Capability | Status |
|---|---|
| Multi-model comparison infrastructure | **PROVEN** |
| Detection count on real footage | **PARTIALLY VALIDATED** |
| Precision/recall by model | **NOT YET VALIDATED** (no ground truth) |
