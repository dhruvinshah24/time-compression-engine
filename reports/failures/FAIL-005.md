# FAIL-005 — COMPRESSION_ERROR

**Severity:** MAJOR  
**Video:** exp_c_fast_motion  
**Stage:** s02_extract  

## Description

On fast_motion_60s.mp4 (60s, burst at t=20-30s), adaptive skip selected only 174 frames (11.6% ratio) vs fixed-5 which selected 300 frames (20% ratio). Within the motion burst region (frames 500-750), adaptive retained 16.3% of frames vs 20.3% for fixed-5. This means adaptive skip MISSED MORE CRITICAL FRAMES than fixed-5 during the most important part of the video.

## Expected

Adaptive skip should retain MORE frames during motion burst than fixed-5

## Actual

Adaptive retained 16.3% of burst frames; fixed-5 retained 20.3%

## Possible Cause

MOG2 warmup (25 frames default) means the first 1 second of motion is not well-detected. The protection_threshold (0.08) may be too high for synthetic motion. Additionally, the adaptive selection overhead was 14.9 seconds — 25% of the 60s video duration.
