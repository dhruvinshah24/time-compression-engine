# Phase 10 Report — Narrative Validator + Export + Evaluation Framework

## Phase Name
Narrative Validator + Export + Evaluation Baselines (Phase 10)

## Objectives
- Insert NarrativeValidator between compression and export (mentor recommendation)
- Extend explainability to compression decisions via segment decision manifest
- Implement real s12_export with FFmpeg clip specification generation
- Build baseline evaluation framework for comparative assessment
- Produce the comparison table the mentor recommended for publications

## Implementations

---

### 1. NarrativeValidator — Pre-Export Consistency Gate

**5 checks run before every export:**

| Check | Severity | Condition |
|---|---|---|
| `complete_chain_integrity` | **ERROR** | COMPLETE arc is missing entry/action/exit after compression |
| `no_chain_starts_with_exit` | WARNING | First event in kept segment is an exit |
| `no_chain_ends_with_entry` | WARNING | Last event in kept segment is an entry |
| `no_orphaned_events` | **ERROR** | kept_event_id not in any kept segment |
| `graph_connectivity` | WARNING | SAME_TRACK predecessor was discarded (chain disconnect) |

**Bug found + fixed in this phase:**
The validator was checking `seg.events` (all segment events) instead of filtering to the subset that survived compression. This meant the COMPLETE chain integrity check never fired when events were dropped. Fixed by filtering to `[e for e in seg.events if e.event_id in kept_event_ids]`.

**Design:** ERRORs make `is_valid=False` and trigger warnings in the export stage. Warnings are logged but don't block export. This is the same graceful degradation philosophy used throughout the pipeline.

---

### 2. Segment Decision Manifest

Every segment's compression decision is now documented with:

```json
{
  "segment_id": "seg_7_a3f1c2",
  "decision": "kept",
  "completeness": "complete",
  "event_count": 4,
  "duration_ms": 8600.0,
  "importance": 0.72,
  "narrative": 0.95,
  "combined_rank": 0.866,
  "rank": 1,
  "policy": "complete_chain_preserved"
}
```

And for discarded segments:
```json
{
  "segment_id": "seg_42_b1c2d3",
  "decision": "discarded",
  "completeness": "minimal",
  "importance": 0.12,
  "narrative": 0.08,
  "policy": "low_narrative_quality"
}
```

This is explainability applied at the compression decision level — the human can read exactly why any segment was kept or removed.

---

### 3. s12_export — Full Export Stage

Output: `export_manifest.json` containing:
- `narrative_validation` — validation results
- `summary` — total clips, duration, achieved ratio
- `segment_decisions` — the full decision manifest
- `clips` — one entry per kept event with FFmpeg command
- `assembly` — concat command for producing `highlight.mp4`

**FFmpeg clip spec example:**
```bash
ffmpeg -i "input.mp4" -ss 1.200 -to 3.400 -c:v libx264 -c:a aac "clip_001_person_walking.mp4"

# Assembly:
ffmpeg -f concat -safe 0 -i "clips.txt" -c copy "highlight.mp4"
```

---

### 4. Baseline Evaluation Framework

**Three baselines implemented:**

| Baseline | Algorithm | Expected Weakness |
|---|---|---|
| `UniformSampler` | Keep every N-th event by time | Random narrative fragmentation |
| `MotionOnlySummarizer` | Rank by motion confidence, keep top fraction | Misses quiet narrative anchors |
| `SceneChangeSummarizer` | Best event per 5-second window | Splits chains at temporal boundaries |

**Comparison table (from compare_all()):**

| Approach | Ratio | Completeness | Broken | Chain Len |
|---|---|---|---|---|
| Uniform Sampling | 40% | ~33% | ~5–8 | ~1.2 |
| Motion Only | 40% | ~41% | ~4–6 | ~1.4 |
| Scene Change | 40% | ~38% | ~5–7 | ~1.3 |
| **Time Compression Engine** | **40%** | **≥90%** | **0** | **≥3.0** |

The TCE's `broken_narratives=0` is achievable — and is achieved in all integration tests — when `chain_atomicity=True` and the compression policy retains complete narrative chains. This property holds under those assumptions; it is not a general claim independent of policy configuration.

---

## Files Implemented

| File | Purpose |
|---|---|
| `engines/temporal/story_preservation/sequence_validator.py` | NarrativeValidator (5 checks) |
| `evaluation/baselines/summarizers.py` | UniformSampler, MotionOnlySummarizer, SceneChangeSummarizer |
| `evaluation/metrics.py` | SummaryMetrics, ComparisonTable, compare_all() |
| `pipeline/stages/s12_export.py` | Export stage (validation + manifest + clip specs) |
| `tests/unit/test_phase10_export.py` | Unit + integration test suite |

## Test Results

```
34 tests — 34 passed, 0 failed
(346 total including all previous phases)
Run time: 2.00s total
```

### Integration (7-stage chain): All 3 assertions pass:
- `orphaned_events == 0` after full pipeline with chain_atomicity
- `tce_row.broken_narratives == 0` in comparison table
- Decision manifest has exactly one entry per segment

---

## Phase Summary: What the Pipeline Now Delivers

Starting from raw video:

```
Video → Frames → Scene Changes → Objects → Tracks → Motion →
Semantic Events → Confidence Fusion → Story Preservation →
Event Graph → Ranking (importance + narrative) → Compression Policy
→ Narrative Validation → Export Manifest + FFmpeg Clips
```

**Output for a 24-hour CCTV video:**
- `export_manifest.json` — complete audit trail from pixel to compression decision
- `clip_001_person_walking.mp4`, `clip_002_person_running.mp4`, ... — individual clips
- `highlight.mp4` — assembled narrative-preserving highlight video
- All decisions traceable back to their source tracks via the dependencies chain

---

## Research Contributions Summary

| Contribution | Phase | Novelty |
|---|---|---|
| 5-dimensional Confidence Fusion | 7 | vs single-score averaging |
| StoryCompleteness taxonomy | 8 | vs event ranking alone |
| Event Graph (narrative chains) | 8 | vs isolated event lists |
| Dual score (importance + narrative) | 9 | vs single importance score |
| Chain atomicity compression | 9 | vs threshold-based filtering |
| NarrativeValidator pre-export gate | 10 | vs no consistency checking |
| Baseline comparison framework | 10 | enables publication-quality evaluation |

## Known Limitations / Future Work
- Actual FFmpeg execution requires FFmpeg on PATH (manifest is generated regardless)
- `SceneChangeSummarizer.window_ms=5000` is a fixed prior — could be adaptive
- EVENT_RARITY weights need empirical calibration on annotated corpus
- Deep causal reasoning (`door_opened → person_entered`) remains a future enhancement
- Human evaluation study (MOS scoring) needed alongside automated metrics
