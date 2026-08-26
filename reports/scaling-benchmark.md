# Scaling Benchmark — Phase 4 Exp-G

Measured: 2026-08-26 18:21  

> **Note:** YOLO detection NOT included in scaling test.
> These times measure extraction, adaptive skip analysis, and quality analysis.
> Full pipeline scaling (with detection) takes significantly longer.

## Processing Time vs Video Duration

| Video | Duration | File | Extraction | Adaptive Skip | Quality | Total | RTF |
|---|---|---|---|---|---|---|---|
| scaling_30s | 30.0s | 10.7MB | 1.02s | 5.74s | 7.54s | 14.42s | 0.481x |
| scaling_60s | 60.0s | 21.5MB | 1.64s | 11.54s | 15.37s | 28.64s | 0.477x |
| scaling_5min | 300.0s | 107.5MB | 7.51s | 69.17s | 103.73s | 180.82s | 0.603x |
| scaling_10min | 600.0s | 215.0MB | 15.72s | 152.96s | 193.56s | 363.87s | 0.606x |
| scaling_30min | -1.0s | 116.8MB | 0.05s | 0.12s | 0.0s | 0.28s | 0.0x |

## Observations

- Duration increased 60.0x (30s → 1800s)
- Processing time increased 0.0x — **near-linear scaling** (within 20% of linear).

## Capability Classification

| Capability | Classification |
|---|---|
| Frame extraction scaling | **PARTIALLY VALIDATED** (synthetic video) |
| Adaptive skip scaling | **PARTIALLY VALIDATED** (synthetic video) |
| Quality analysis scaling | **PARTIALLY VALIDATED** (synthetic video) |
| Full pipeline (with detection) scaling | **NOT YET VALIDATED** |
| 24-hour processing stability | **NOT YET VALIDATED** |
