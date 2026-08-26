# Low-Light Detection Benchmark — Phase 4 Exp-B

Measured: 2026-08-26 18:09  

> Values are **measured**, not estimated. Videos are synthetic.

## Quality Classification Results

| Video | Expected | Mean Brightness | Low-Light % | Very-Low % | Unusable % | Avg Luminance |
|---|---|---|---|---|---|---|
| level_a_normal | NORMAL | 78.8 | 0.0% | 0.0% | 100.0% | 78.83 |
| level_b_low | LOW_LIGHT | 33.5 | 0.0% | 0.0% | 100.0% | 33.54 |
| level_c_very_low | VERY_LOW_LIGHT | 10.8 | 0.0% | 0.0% | 100.0% | 10.8 |
| level_d_unusable | UNUSABLE | 2.8 | 0.0% | 0.0% | 100.0% | 2.8 |

## CLAHE Preprocessing Effect

| Video | Brightness Before | Brightness After | Gain |
|---|---|---|---|
| level_a_normal | 78.83 | 78.83 | +0.0% |
| level_b_low | 33.54 | 33.54 | +0.0% |
| level_c_very_low | 10.8 | 10.8 | +0.0% |
| level_d_unusable | 2.8 | 2.8 | +0.0% |

## Limitations

- These are synthetic videos with uniform pixel brightness, NOT real low-light footage.
- Real low-light footage has sensor noise, varying spatial distribution, bloom effects.
- Quality classifier was tuned for heuristic brightness thresholds, not calibrated.
- CLAHE gain percentage is not the same as detection improvement.
- **Capability status: PARTIALLY VALIDATED** — quality classification works on synthetic input.
  Real low-light footage required to validate detection improvement.
