# Phase 9 Report — Ranking Engine + Compression Policy

## Phase Name
Ranking Engine + Compression Policy (Phase 9)

## Objectives
- Implement mentor's core recommendation: Importance Score and Narrative Value Score as independent dimensions
- Rank story segments as atomic units (chains), not individual events
- Apply compression policy that preserves narrative coherence over raw importance
- Produce evaluation metrics for the assessment chapter
- Prevent narrative fragmentation via chain atomicity

## Pre-Phase 9 Addition

### ConfidenceVector `components` grouping
`ConfidenceVector.to_dict()` now exposes both a flat structure (backward compatibility) and a grouped `components` dict showing all 5 dimensions alongside the fused score. This implements the mentor's recommendation from Phase 7's review.

## Algorithm: Two Independent Score Dimensions

**The core design principle (per mentor guidance):**

> A person standing still for 5 seconds:
> - Importance: 0.25 (not visually exciting)
> - Narrative: 0.90 (removing it makes the next event inexplicable)
>
> A flashing light:
> - Importance: 0.80 (visually salient)
> - Narrative: 0.10 (irrelevant to the story)

These are computed and stored independently.

---

### Importance Score — 4 components

| Component | Source | Meaning |
|---|---|---|
| `detection` | `event.confidence` (fused by Phase 7) | How clearly was the object seen? |
| `rarity` | `EVENT_RARITY` lookup table | How uncommon is this event type? |
| `motion` | `motion_profile.avg_speed_per_second` | How fast was the object moving? |
| `salience` | Detection confidence proxy | How visually prominent was the object? |

**Formula:** `0.35×detection + 0.35×rarity + 0.20×motion + 0.10×salience`

**EVENT_RARITY table (key entries):**
| Event | Rarity |
|---|---|
| person_running | 0.90 |
| person_loitering | 0.80 |
| vehicle_approaching | 0.75 |
| person_walking | 0.50 |
| person_standing | 0.30 |

---

### Narrative Score
Carried forward from Phase 8 StoryBuilder. Not recomputed.

---

### Combined Rank
```
combined_rank = 0.40 × importance_score + 0.60 × narrative_score
```
Default weights: narrative weighted higher (60%) than importance (40%).
Rationale: preserving narrative coherence is more valuable than visual excitement.
Configurable via `rank_w_importance` / `rank_w_narrative` in system_settings.

---

### Compression Policy — Chain Atomicity

**Key invariant (per mentor):** "Entry → Walk → Pickup → Exit should survive or disappear as a unit."

**4-step algorithm:**
1. **Quality gate:** Discard segments with `narrative_score < completeness_min_threshold` (default 0.20)
2. **COMPLETE preservation:** If `always_keep_complete=True`, all COMPLETE arcs are unconditionally kept
3. **Ratio cut:** From remaining candidates, keep top segments by `combined_rank` until `target_ratio` budget (default 40%) is reached
4. **Chain atomicity:** Each segment's events are kept or discarded together — never split mid-chain

**CompressionDecision.reason** (the explainability audit trail):
- `"complete_chain_preserved"` — COMPLETE arc always kept
- `"high_combined_rank"` — survived ratio cut
- `"below_ratio_threshold"` — discarded to meet target
- `"low_narrative_quality"` — below quality gate

---

## Evaluation Metrics (per mentor recommendation)

These metrics appear in every compression result and will be the foundation of the evaluation chapter:

| Metric | Meaning |
|---|---|
| `story_completeness_retained` | Fraction of COMPLETE arcs that survived compression |
| `broken_narratives` | Segments where chain atomicity was violated (target: 0) |
| `avg_narrative_chain_length` | Mean events per kept segment (higher = richer output) |
| `compression_ratio_achieved` | Actual kept/total ratio vs target |

---

## Files Implemented

| File | Purpose |
|---|---|
| `engines/temporal/ranking_engine/config.py` | RankingConfig with weight validation |
| `engines/temporal/ranking_engine/ranker.py` | RankingEngine, ImportanceScore, RankedSegment, EVENT_RARITY |
| `engines/temporal/compression_policy/config.py` | CompressionConfig |
| `engines/temporal/compression_policy/policy.py` | CompressionPolicy, CompressionDecision, CompressionResult |
| `pipeline/stages/s10_rank.py` | Ranking pipeline stage |
| `pipeline/stages/s11_summarize.py` | Compression policy pipeline stage |
| `tests/unit/test_ranking_compression.py` | Unit + integration test suite |

## Test Results

```
39 tests — 39 passed, 0 failed
(312 total including all previous phases)
Run time: 1.98s total
```

### Integration tests (full 6-stage chain: Track → Motion → Event → Fusion → Story → Rank → Compress):

| Test | Expected | Result |
|---|---|---|
| Every event has a decision | decision count = event count | ✅ |
| Every decision has reason | reason in valid set | ✅ |
| running > standing importance | EVENT_RARITY ordering | ✅ |
| compression_ratio in [0, 1] | 0.0 ≤ ratio ≤ 1.0 | ✅ |
| All evaluation metrics present | Keys in metrics dict | ✅ |

### Bug fixed during Phase 9
`_record_segment` did not add segment_id to `discarded_segment_ids` for discard calls because the guard `if keep:` prevented it. Fixed by removing the conditional — the caller already passes the correct set.

## Phase 10 Preview
The compression result feeds directly into `s12_export.py` which will:
- Extract video clips for each `summary_events` entry using FFmpeg
- Produce a final highlight video with narrative ordering
- Output a JSON manifest for the frontend

## Known Issues / Limitations
- `EVENT_RARITY` values are manually assigned priors. Phase 10 (Evaluation) should update these from corpus statistics.
- `max_motion_intensity=0.05` (normalized units/sec) is an empirical default. Calibrate per domain (e.g. highway dashcam vs indoor corridor).
- The `target_ratio` budget check is greedy (first-fit). Optimal bin-packing would give a more precise ratio. This is acceptable for Phase 9.

## Dependencies Added
- None. Pure Python + NumPy.
