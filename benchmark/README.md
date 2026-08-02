# Benchmarking Framework

This directory contains the tools and configurations required to evaluate the performance of the Time Compression Engine (TCE) against its core targets.

## Purpose
While the `evaluation/` folder focuses on the *accuracy* and *quality* of the output (e.g., Narrative Preservation Score, F1), the `benchmark/` folder focuses on system-level performance. We measure throughput, compression efficiency, and resource utilization.

## How to Run Benchmarks

*Note: The benchmarking scripts are stubbed for Phase 1 and will be implemented in later phases.*

1. **Prepare Data**: Ensure your evaluation dataset is loaded and available.
2. **Execute**:
   ```bash
   python run_benchmarks.py --dataset indoor_office_v1 --hw_profile gpu_rtx3090
   ```
3. **Output**: The system will generate a markdown report detailing the performance against the target metrics.

## Key Focus Areas
- **Throughput**: Can the system process video faster than real-time (e.g., >30fps)?
- **Compression**: Does the system consistently hit extreme compression targets (>100:1) on sparse event videos (e.g., overnight security footage)?
- **Scalability**: How does memory usage grow as the Event Graph increases in size over a 24-hour continuous video feed?
