# Adaptive Skip Diagnostic — Phase 5B

Measured: 2026-09-05 22:52  

> **Research question:** Why did Phase 4 find adaptive retained only 16.3% of burst frames vs fixed-5's 20.3%?

## Phase 4 Reference Results

| Strategy | Selected | Ratio | Burst Retention | Overhead |
|---|---|---|---|---|
| fixed_skip_1 | 1500 | 100.0% | 100.0% | 5ms |
| fixed_skip_5 | 300 | 20.0% | 20.3% | 4ms |
| adaptive_mog2 (baseline) | 174 | 11.6% | **16.3%** | 14,866ms |

## Phase 5B Variant Comparison

| Variant | Selected | Ratio | Burst Retention | Overhead | warmup | prot_thresh | prot_window |
|---|---|---|---|---|---|---|---|
| baseline | 177 | 11.8% | 11.6% | 9.88s | 25 | 0.08 | 15 |
| conservative | 199 | 13.3% | 13.5% | 9.37s | 10 | 0.05 | 25 |
| aggressive | 111 | 7.4% | 9.2% | 10.27s | 5 | 0.12 | 10 |

## Root Cause Analysis

### baseline

```
  Burst detection delay: 11 frames (0.44s) after burst start
  First non-STATIC frame in burst: frame 511 tier=LOW raw=1.42% ema=1.07%
  Burst frames classified STATIC: 192/251 (76.5%)
  Burst frames selected: 29/251 (11.6%)
  Burst frames NOT selected: 222
```

### conservative

```
  Burst detection delay: 10 frames (0.40s) after burst start
  First non-STATIC frame in burst: frame 510 tier=LOW raw=1.3% ema=1.03%
  Burst frames classified STATIC: 192/251 (76.5%)
  Burst frames selected: 34/251 (13.5%)
  Burst frames NOT selected: 217
```

### aggressive

```
  Burst detection delay: 12 frames (0.48s) after burst start
  First non-STATIC frame in burst: frame 512 tier=LOW raw=1.53% ema=1.09%
  Burst frames classified STATIC: 192/251 (76.5%)
  Burst frames selected: 23/251 (9.2%)
  Burst frames NOT selected: 228
```

## Conclusions

- Best burst retention: **conservative** (13.5%)
- Worst burst retention: **aggressive** (9.2%)
- All variants still underperform fixed-5 (20.3%) on this synthetic video.
- The primary cause is EMA lag: by the time EMA detects motion, several burst frames have already been skipped.
- **Recommendation:** Validate on real CCTV footage before changing defaults. Synthetic rectangle motion may not be representative.

## Capability Classification

| Capability | Classification |
|---|---|
| Adaptive skip infrastructure | **IMPLEMENTED** |
| Adaptive skip on synthetic burst | **PARTIALLY VALIDATED** — underperforms fixed-5 |
| Adaptive skip on real CCTV footage | **NOT YET VALIDATED** |
| Parameter tuning for real content | **NOT YET VALIDATED** |
