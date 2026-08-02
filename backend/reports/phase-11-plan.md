# Phase 11 Plan — Experimental Validation

## Goal
Validate the Time Compression Engine against annotated benchmark videos and
produce quantitative evidence of improvement over the three baselines.

This is the phase that transforms a well-built system into a defensible
research contribution.

---

## Benchmark Corpus

### Recommended datasets

| Dataset | Domain | Why suitable |
|---|---|---|
| [SumMe](https://gyglim.github.io/me/vsum/index.html) | General (user videos) | Ground-truth highlights + narrative annotations |
| [TVSum](https://github.com/yalesong/tvsum) | News, how-to, sports | Frame-level importance scores |
| [UCF-Crime](https://www.crcv.ucf.edu/projects/real-world/) | CCTV anomalies | Closest to target domain (surveillance) |
| In-house CCTV clips | Parking lot, corridor | Custom annotation for narrative labels |

**Minimum viable corpus:** 10 videos × 5–30 minutes each = ~5 hours of annotated video.

### Annotation protocol
For each video, annotators label:
1. **Event boundaries** — start_ms / end_ms for each real-world event
2. **Story arc completeness** — COMPLETE / PARTIAL / MINIMAL per track
3. **Highlight importance** — 1–5 scale per event (for precision/recall)
4. **Narrative coherence** — does the summary make sense as a standalone video? (MOS 1–5)

---

## Evaluation Protocol

### Quantitative metrics (automated)

| Metric | Formula | What it measures |
|---|---|---|
| **Precision** | TP / (TP + FP) | Are kept events actually important? |
| **Recall** | TP / (TP + FN) | Are important events kept? |
| **F1** | 2 × P × R / (P + R) | Balanced accuracy |
| **Compression Ratio** | kept_ms / total_ms | Degree of compression achieved |
| **Narrative Preservation** | complete_chains_retained / total_complete | Story coherence retained |
| **Broken Narratives** | count of partial chains in output | Fragmentation |
| **Avg Chain Length** | mean events per kept segment | Richness of kept stories |

### Qualitative metric (human evaluation)

**Mean Opinion Score (MOS)**
- Show 5 evaluators: original video, TCE summary, uniform sampling summary
- Rate each summary: 1 (terrible) to 5 (excellent)
- Question: "Does this summary tell the complete story of what happened?"

---

## Comparison Table (target format)

| Approach | Precision | Recall | F1 | Ratio | Narrative | Broken | MOS |
|---|---|---|---|---|---|---|---|
| Uniform Sampling | | | | 40% | | | |
| Motion Only | | | | 40% | | | |
| Scene Change | | | | 40% | | | |
| **TCE (ours)** | | | | 40% | | | |

Fill in after benchmark runs. Export using `compare_all()` in `evaluation/metrics.py`.

---

## Implementation Checklist

- [x] **Freeze TCE v1.0 reference configuration** — `TCE_V1_REFERENCE` in `evaluation/reference_config.py` (immutable, validated, JSON-serialisable)
- [ ] Select and download benchmark corpus
- [ ] Create annotation tool / import existing annotation format (SumMe JSON)
- [ ] Write `evaluation/benchmark_runner.py`:
  - Loads annotated video + ground truth
  - Runs full TCE pipeline using `TCE_V1_REFERENCE.to_pipeline_settings()`
  - Embeds `TCE_V1_REFERENCE.to_dict()` in every result file
  - Runs all 3 baselines at same `compression_target_ratio`
  - Calls `compare_all()` and saves ComparisonTable to `reports/benchmark/`
- [ ] Run benchmarks across all videos **without changing any config**
- [ ] **Populate failure catalogue** — for every incorrect result, add a `FailureRecord` with category + severity + improvement_hypothesis
- [ ] Aggregate results (mean ± std across videos)
- [ ] Conduct MOS study with 3–5 evaluators
- [ ] Run `catalogue.summary()` to identify `most_common_failure` and `most_implicated_stage`
- [ ] Write `reports/phase-11-results.md` with full table + failure analysis + limitations section
- [ ] Only then: create variants with `TCE_V1_REFERENCE.variant(...)` and benchmark each change against v1.0

---

## Failure Catalogue (mandatory deliverable)

Per mentor recommendation: collect and classify every failure, not just aggregate metrics.

> "That failure catalogue often becomes one of the most valuable sections of a research
>  report because it naturally motivates future work."

The six failure categories (implemented in `evaluation/failure_catalogue.py`):

| Category | Example | Improvement direction |
|---|---|---|
| `MISSED_EVENT` | Person entered but not detected | Higher detection sensitivity / tracking recall |
| `FALSE_EVENT` | Camera shake classified as movement | Stricter rule conditions / confidence threshold |
| `TRACKING_FAILURE` | Track switched identities mid-scene | SORT/DeepSORT, add ReID module |
| `STORY_BREAK` | Complete chain incorrectly split | Tune `chain_atomicity` / `completeness_min_threshold` |
| `COMPRESSION_ERROR` | Important segment was discarded | Adjust `w_narrative` / `target_ratio` |
| `VALIDATOR_WARNING` | NarrativeValidator flagged inconsistency | Review compression_policy configuration |

**Four-level severity scale (per mentor recommendation):**

| Severity | Meaning |
|---|---|
| `CRITICAL` | Changes the narrative or produces an incorrect summary |
| `MAJOR` | Loses an important event but overall story remains understandable |
| `MINOR` | Cosmetic or low-impact issue |
| `INFORMATIONAL` | Worth noting but doesn't affect the final summary |

Distinguishing severity matters: a `MISSED_EVENT / INFORMATIONAL` (minor clutter) is categorically different from a `MISSED_EVENT / CRITICAL` (the entire reason a person was in the scene went unrecorded).

**Workflow:**
```python
from app.evaluation.failure_catalogue import FailureCatalogue, FailureRecord, FailureCategory, FailureSeverity

catalogue = FailureCatalogue()
catalogue.add(FailureRecord(
    video_id="ucf_crime_001",
    timestamp_ms=4200.0,
    category=FailureCategory.MISSED_EVENT,
    severity=FailureSeverity.CRITICAL,
    description="Person entered at 4.2s — not detected.",
    ground_truth="PERSON_ENTERED_SCENE at 4200ms",
    pipeline_output="No event produced for track_id=3",
    pipeline_stage="s04_object_detect",
    improvement_hypothesis="YOLOv8n confidence threshold too high for low-light entry",
))
catalogue.save("reports/failures/ucf_crime_001.json")
print(catalogue.to_markdown_table())
```

**Report section target:** After running all benchmark videos, produce one aggregate catalogue. The `most_common_failure` and `most_implicated_stage` fields directly write the "Limitations and Future Work" section.

---


1. **Does narrative preservation improve with TCE vs baselines?**
   Hypothesis: TCE retains ≥2× more COMPLETE chains than uniform sampling at the same compression ratio.

2. **Does chain atomicity reduce broken narratives to near-zero in practice?**
   Hypothesis: With `chain_atomicity=True`, broken_narratives ≤ 5% of chains vs 30–50% for baselines.

3. **Is there a precision-recall tradeoff vs compression ratio?**
   Experiment: Run TCE at `target_ratio` ∈ {0.20, 0.30, 0.40, 0.50, 0.60} and plot P-R curve.

4. **Which fusion strategy (weighted_linear / geometric / harmonic / min) best correlates with human MOS?**
   Experiment: Run same video through all 4 strategies, compare MOS scores.

5. **Which confidence dimension is most predictive of event importance?**
   Analysis: Pearson correlation between each dimension (detection/motion/rule/track/scene) and human importance ratings.

---

## Per-Mentor Calibration Notes

> "Be careful with statements like 'broken_narratives = 0 (guaranteed)'."

The correct claim is:
> "When `chain_atomicity=True` and the compression policy retains complete narrative chains,
>  the NarrativeValidator is designed to prevent broken narratives in the exported result.
>  This property holds under those assumptions and was observed in all integration tests.
>  Benchmark results will show whether it holds at scale on real-world footage."

---

## Phase 11 Timeline Estimate

| Task | Estimated Time |
|---|---|
| Dataset acquisition + setup | 1–2 days |
| Annotation (10 videos) | 2–3 days (with 2 annotators) |
| BenchmarkRunner implementation | 1 day |
| Running benchmarks | 1–2 hours (automated) |
| MOS study | 1–2 days |
| Analysis + report writing | 1–2 days |
| **Total** | **~8–12 days** |
