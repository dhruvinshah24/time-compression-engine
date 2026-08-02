# Formal Research Contributions

The Time Compression Engine (TCE) is positioned as a research-grade system. This document formalizes the novel contributions it makes to the field of automated video summarization and semantic analysis.

## 1. Problem Framing: Semantic Temporal Compression
Standard video summarization relies heavily on low-level features (motion magnitude, simple object detection). TCE reframes the problem as **Semantic Temporal Compression**, where compression ratios are achieved by extracting high-level meaning rather than just pixel variance. This shifts the focus from "where is there movement?" to "what is happening and does it matter?"

## 2. Three-Engine Architecture
The explicit decoupling of Perception (pixels to signals), Semantic Intelligence (signals to events), and Temporal Intelligence (events to narrative) provides a highly modular and extensible framework. This separation of concerns allows for the rapid swapping of state-of-the-art vision models in the Perception layer without rewriting the core business logic of the Temporal layer.

## 3. Story Preservation as a Computational Problem
Traditional summarization often results in a disjointed "highlight reel" where the context is lost. TCE introduces **Story Preservation** as a core computational metric. By ensuring that if an event $E$ is included, its causal prerequisite $C(E)$ is also evaluated for inclusion, the system maintains narrative coherence.

## 4. Event Graph vs. Flat Timeline
Most systems model video events as a flat list of timestamps $[(t_{start}, t_{end}, label), ...]$. TCE models video as a Directed Graph $G = (V, E)$, where vertices are semantic events and edges denote causality, spatial proximity, or temporal sequence. This allows for advanced graph algorithms (like subgraph extraction) to drive the compression policy.

## 5. Multi-Signal Confidence Fusion Methodology
Confidence scores from Neural Networks are notoriously uncalibrated. TCE introduces a fusion methodology that combines bounding box confidence, tracking stability (ID switch frequency), scene context, and rule-satisfaction strictness into a single, calibrated metric that better reflects real-world probability.

## 6. Evaluation Framework & Narrative Metric
TCE introduces a specialized evaluation framework for video summarization that goes beyond standard F1 scores. The `narrative_preservation_score` directly quantifies how well the generated summary maintains the causal event chains present in the ground-truth annotations, providing a new benchmark for summarization quality.
