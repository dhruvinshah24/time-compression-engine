# Benchmark Metrics

| Metric | Formula | Target | Unit |
|---|---|---|---|
| Compression Ratio | input_sec / output_sec | > 100:1 | ratio |
| Temporal Precision | relevant_kept / total_kept | > 90% | % |
| Temporal Recall | relevant_kept / total_relevant | > 85% | % |
| F1 Score | 2*P*R/(P+R) | > 87% | % |
| Event Coverage | detected / ground_truth | > 90% | % |
| Narrative Score | coherent_chains / total_chains | > 80% | % |
| Processing Speed | frames / second | > 30 FPS | fps |
| Storage Saved | (orig - compressed) / orig | > 95% | % |
