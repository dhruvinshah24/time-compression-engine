# Adaptive Skip Comparison — Phase 4 Exp-F

Measured: 2026-08-26 18:06  
Video: `fast_motion_60s.mp4` (1500 frames, 60s @ 25fps)  
Motion burst region: frames 500–750 (t=20s–30s)  

> All values are **measured**, not estimated.

## Results Table

| Strategy | Frames Selected | Ratio | Selection Time | Burst Retention |
|---|---|---|---|---|
| fixed_skip_1 | 1500 of 1500 | 100.0% | 5ms | 100.0% |
| fixed_skip_5 | 300 of 1500 | 20.0% | 4ms | 20.3% |
| adaptive_mog2 | 174 of 1500 | 11.6% | 14866ms | 16.3% |

## Burst Region Detail

The motion burst (frames 500–750) is where a 'person' moves rapidly.
Critical frame retention = fraction of burst frames that were selected.

| Strategy | Burst Frames Selected | Burst Total | Retention |
|---|---|---|---|
| fixed_skip_1 | 251 | 251 | 100.0% |
| fixed_skip_5 | 51 | 251 | 20.3% |
| adaptive_mog2 | 41 | 251 | 16.3% |

## Adaptive Skip Internal Stats

- Protection windows triggered: **0**
- Protected frames: **0**
- Average motion score: **0.23%**
- Max motion score: **100.00%**
- Tier distribution: {'MEDIUM_MOTION': 25, 'STATIC': 1215, 'LOW_MOTION': 260}

## Observations

- Adaptive selected 174 frames vs 300 for fixed-5 (fewer frames).
- Burst retention: adaptive=16.3%, fixed-5=20.3%. Fixed-5 preserved more critical frames — investigate protection threshold.
- Selection overhead: adaptive=14866ms vs fixed-5=4ms (streaming cost).

## Limitations

- This experiment uses synthetic pixel motion (moving rectangle), NOT real scene content.
- MOG2 detects pixel change, not semantic events. Results may differ on real footage.
- Events missed cannot be quantified without YOLO detections on real people.
- **Capability status: PARTIALLY VALIDATED** — measured on synthetic video. Real-footage validation required to confirm event preservation.
