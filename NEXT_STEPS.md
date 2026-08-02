# TCE v1.0.0 — What Comes Next

```
Status: v1.0.0 (Reference Implementation)

Implementation:              COMPLETE
Testing:                     COMPLETE  (379/379 passing)
Evaluation Infrastructure:   COMPLETE
Benchmarking:                NOT STARTED

Current Objective:
Empirically evaluate TCE v1.0 against baseline methods.
```

> The code is done. Ask it with real footage.

This file contains the only prompts worth running after `v1.0.0` is tagged.
It also lists the prompts that should be deliberately avoided until benchmark
results justify them.

---

## The single most important prompt

> Run the complete benchmark suite on TCE v1.0, compare against all three
> baselines, generate the full evaluation report, and do not change a single
> line of implementation code. Base every conclusion only on measured evidence,
> clearly distinguishing observations from interpretations.

That prompt marks the transition from software engineering to research.
Everything after it should be driven by data, not new ideas.

---

## Remaining prompts — in priority order

### 1. Benchmark Runner *(Highest priority)*

> Build a benchmark runner that executes TCE v1.0 on every video listed in
> `datasets/benchmarks/manifest.json`. For each video, automatically generate
> a benchmark result JSON in the appropriate `results/TCE-v1.0/` directory
> containing:
>
> - reference configuration (`ReferenceConfig.to_dict()`)
> - git commit
> - processing time
> - pipeline metrics
> - evaluation metrics
> - failure catalogue summary
> - paths to generated outputs
>
> The runner must continue after failures, log errors cleanly, and produce a
> final aggregate summary across the entire benchmark corpus.

**Why first:** Without a runner, benchmark results require manual work per
video. That introduces inconsistency and slows everything down.

---

### 2. Ground Truth Annotation Tool

> Build a lightweight annotation tool for creating ground-truth event timelines.
>
> Requirements:
> - Play video, pause, frame-step
> - Mark event start/end
> - Select event type from `knowledge/v1/event_taxonomy.json`
> - Export JSON matching the taxonomy schema
> - Keyboard shortcuts for speed
>
> This tool will be used only by human annotators to create benchmark labels.

**Why second:** Without good ground truth, Precision/Recall/F1 are meaningless.
The annotation format should be locked to the existing event taxonomy — no
new event types should be invented during annotation.

---

### 3. Evaluation Report Generator

> Build an automated report generator that reads every benchmark JSON and
> produces:
>
> - Precision / Recall / F1 tables
> - Narrative Preservation statistics
> - Compression Ratio distributions
> - Failure Catalogue summaries
> - Baseline comparison tables
> - Markdown report ready to include in the dissertation

**Output:** `reports/phase-11-results.md` — a single document the dissertation
can reference directly.

---

### 4. Visualization Dashboard *(Read-only)*

> Build an evaluation dashboard that visualizes:
>
> - benchmark results
> - compression ratios
> - confidence distributions
> - event frequencies
> - failure categories
> - narrative preservation scores
>
> The dashboard is read-only and intended for analysis, not system control.

**Note:** Build only after the runner and annotation tool produce real data.
A dashboard over empty results directories has no value.

---

### 5. Ablation Framework

> Build an experiment runner capable of executing named configuration variants
> (e.g. `TCE-v1.1-geometric`) while preserving TCE v1.0 as the immutable
> reference.
>
> Automatically compare each variant against the reference and generate delta
> reports showing which metrics improved, degraded, or remained unchanged.

**Pre-condition:** Do not build this until v1.0.0 benchmark results exist.
There is nothing to compare against until the baseline is measured.

---

### 6. Dissertation Figures *(Can be done in parallel)*

> Automatically generate publication-quality figures (SVG/PDF) for:
>
> - Pipeline architecture
> - Three-engine architecture diagram
> - Event graph example
> - Confidence fusion dimensions
> - Benchmark comparison charts
> - Failure category distribution
> - Narrative preservation examples

**Note:** Architecture figures can be generated now from existing code.
Result figures must wait until benchmark data exists.

---

## Prompts to deliberately avoid until v1.1 is justified by evidence

```
❌  "Add another AI model"
❌  "Support a different detector"
❌  "Add GPT / LLM reasoning"
❌  "Improve the architecture"
❌  "Add more pipeline stages"
❌  "Increase test coverage further"
❌  "Optimise performance"
```

These belong to **v1.1** — and only if benchmark results demonstrate a clear,
measurable need. Adding them now would make the project larger without making
it more convincing.

---

## The principle behind this list

> Every important decision should be reproducible, explainable, and measurable.

Applied to research methodology:

> Every new feature should be motivated by evidence, not intuition.

---

## Development methodology (final form)

```
Define
  ↓
Design
  ↓
Build incrementally
  ↓
Test
  ↓
Explain
  ↓
Evaluate
  ↓
Freeze
  ↓
Validate
  ↓
Iterate  ← only if evidence justifies it
```

---

## Branch naming convention for experiments

```
v1.0.0  (tag — immutable reference)
│
├── experiment/geometric-fusion
├── experiment/adaptive-ranking
├── experiment/story-gap-2500ms
│
└── v1.1.0  ← created only after experiments
              demonstrate measurable improvement
```

Never work directly on `main` after `v1.0.0` is tagged.
Every change is an experiment until data promotes it.

---

## Decision Rule

No implementation changes are made on `main` after `v1.0.0`.

Any proposed improvement must satisfy **all** of the following before
it can be considered for a future release:

- [ ] Motivated by benchmark evidence (not intuition)
- [ ] Implemented on an `experiment/*` branch
- [ ] Compared against TCE v1.0 on the same benchmark corpus
- [ ] Demonstrates measurable improvement on at least one key metric
- [ ] Documents any new limitations introduced

If any box is unchecked, the change is not ready.
