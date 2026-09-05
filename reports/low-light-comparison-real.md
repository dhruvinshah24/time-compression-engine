# Low-Light Comparison — Phase 5E

Clip: `53224_Night_Driving.mp4` first 120s | 640x360 @ 24.0fps  
Measured: 2026-09-05 23:12  

| Metric | Without Preprocessing | With Preprocessing | Delta |
|---|---|---|---|
| Total detections | 246 | 240 | -6 |
| Frames with persons | 21.7% | 22.2% | — |
| Max simultaneous | 10 | 9 | — |
| Processing time | 10.55s | 10.88s | — |
| RTF | 0.088x | 0.091x | — |
| Preprocessing overhead | N/A | 5.57ms/frame | — |

## Conclusion

**REDUCED — preprocessing reduced detections on this night footage**  
Detection change: -2.4%

## Capability Classification

| Capability | Status |
|---|---|
| Low-light preprocessing improves detection | **FAILED** on this footage — reduced detections |
| Modern night CCTV preprocessing | **NOT YET VALIDATED** — no modern night footage |
