# Patent Research Notes

> This document tracks potential novel contributions as they evolve. 
> Maintained incrementally — one entry per phase.

## Potential Novel Contributions

### 1. Confidence Fusion Methodology
**Status**: Architecture defined (Phase 1)
**Description**: Multi-signal confidence aggregation that combines object detection confidence, motion confidence, scene change confidence, tracking confidence, and semantic event confidence into a single weighted fused score.
**Potential claim**: The specific weighting and combination methodology across heterogeneous signal types.

### 2. Semantic Event Selection Strategy  
**Status**: Architecture defined (Phase 1)
**Description**: Knowledge-graph-backed event labelling using hybrid rule-based and LLM reasoning, cross-referenced against a structured event taxonomy.
**Potential claim**: The event selection pipeline that maps low-level perception signals to high-level semantic event labels using a versioned knowledge base.

### 3. Narrative-Preserving Temporal Compression
**Status**: Architecture defined (Phase 1)
**Description**: A story preservation layer that identifies causal event sequences and ensures the compressed video output maintains the narrative coherence of the original recording.
**Potential claim**: The algorithm for identifying and preserving event chains that form a coherent narrative, as distinct from simple importance ranking.

### 4. Explainable Event Selection Pipeline
**Status**: Architecture defined (Phase 1)
**Description**: Every event selection or rejection decision is accompanied by a full reasoning chain documenting which signals triggered the decision, their individual weights, and the final fused confidence.
**Potential claim**: The structured explainability chain format and its integration into the compression decision process.

### 5. Event Graph Representation for Video Summarization
**Status**: Architecture defined (Phase 1)
**Description**: Modelling video events as a directed graph with typed edges (caused_by, followed_by, concurrent, implies) rather than a flat timestamp list.
**Potential claim**: The event graph schema and its use in driving compression policy decisions.

---

## Notes
- Do not make patent claims without professional legal review.
- Document every algorithmic decision as it is implemented.
- Keep this file updated after each phase.
