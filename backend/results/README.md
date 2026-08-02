# Benchmark Results

This directory holds all experimental results for the Time Compression Engine.

## Structure

```
results/
├── TCE-v1.0/           ← All runs using the frozen reference configuration
│   ├── benchmark-001.json
│   ├── benchmark-002.json
│   └── ...
├── TCE-v1.1-geometric/ ← Created only after v1.0 baseline is complete
├── TCE-v1.2-adaptive/  ← Created only after v1.0 baseline is complete
├── motion-only/        ← Baseline: MotionOnlySummarizer results
├── scene-change/       ← Baseline: SceneChangeSummarizer results
└── uniform/            ← Baseline: UniformSampler results
```

> **Rule:** Do not create any `TCE-v1.x` variant directories until the full
> TCE-v1.0 baseline is complete. Every improvement must be measured against
> a stable reference, not a moving target.

---

## Each Result File Answers Four Questions

Every `benchmark-NNN.json` must answer:

| Question | Field |
|---|---|
| What **code** produced this? | `config.git_commit` |
| What **settings** produced this? | `config` (full ReferenceConfig dump) |
| What **data** was processed? | `dataset.video_id`, `dataset.source` |
| What **happened**? | `metrics`, `failure_catalogue_path` |

### Template

```json
{
  "config": {
    "version": "v1.0",
    "git_commit": "a1b2c3d",
    "frame_skip": 5,
    "detection_threshold": 0.72,
    "fusion": {
      "strategy": "weighted_linear",
      "weights": { "detection": 0.25, "motion": 0.20, "rule": 0.25,
                   "track_stability": 0.20, "scene_reliability": 0.10 }
    },
    "story": { "gap_threshold_ms": 5000.0 },
    "ranking": { "w_importance": 0.40, "w_narrative": 0.60 },
    "compression": {
      "target_ratio": 0.40,
      "keep_complete": true,
      "chain_atomicity": true,
      "min_threshold": 0.20
    }
  },
  "dataset": {
    "video_id": "ucf_crime_001",
    "source": "UCF-Crime",
    "duration_s": 180.0,
    "annotator": "annotator_1"
  },
  "metrics": {
    "precision": null,
    "recall": null,
    "f1": null,
    "compression_ratio": null,
    "story_completeness_retained": null,
    "broken_narratives": null,
    "avg_chain_length": null,
    "mos_score": null
  },
  "failure_catalogue_path": "reports/failures/ucf_crime_001.json",
  "export_manifest_path": "results/TCE-v1.0/ucf_crime_001_manifest.json"
}
```

Generate via:
```python
from app.evaluation.reference_config import TCE_V1_REFERENCE
from app.evaluation.metrics import compare_all

result = {
    "config": TCE_V1_REFERENCE.to_dict(),   # git_commit + all params
    "dataset": { "video_id": video_id, ... },
    "metrics": compare_all(...).rows[-1].to_dict(),
    "failure_catalogue_path": ...,
}
```

---

## Benchmark Order

1. Run all videos through **TCE-v1.0** → populate `results/TCE-v1.0/`
2. Run all videos through each baseline → populate `results/motion-only/`,
   `results/scene-change/`, `results/uniform/`
3. Aggregate with `compare_all()` → write `reports/phase-11-results.md`
4. Populate failure catalogue → write `reports/failures/<video_id>.json`
5. Only then: create a named variant like `TCE-v1.1-geometric/` and repeat

---

## Naming Convention

`benchmark-NNN.json` — sequential, padded to 3 digits.  
`NNN` is assigned in processing order, not by importance.

Do not rename files after the fact. The index in the filename is the only
stable identifier for cross-referencing with failure catalogues.
