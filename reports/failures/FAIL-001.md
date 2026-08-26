# FAIL-001 — VALIDATOR_WARNING

**Severity:** MAJOR  
**Video:** all_low_light_levels  
**Stage:** s04_object_detect  

## Description

Quality classifier classifies ALL synthetic frames as UNUSABLE regardless of brightness level (78.8/255 → UNUSABLE, 33.5/255 → UNUSABLE, 10.8/255 → UNUSABLE, 2.8/255 → UNUSABLE). Root cause: Laplacian blur score is near-zero for solid-color synthetic frames. The unusable_blur_score threshold (15.0) fires on every frame. This is classifier-correct behaviour on synthetic input but means quality classification cannot be validated using these test videos.

## Expected

level_a_normal → NORMAL, level_b_low → LOW_LIGHT, level_c_very_low → VERY_LOW_LIGHT

## Actual

All 4 levels → UNUSABLE (0% LOW_LIGHT, 0% VERY_LOW_LIGHT, 100% UNUSABLE)

## Possible Cause

Laplacian variance on solid-color frames ≈ 0. The QualityThresholds.unusable_blur_score=15.0 threshold triggers. Real surveillance frames have texture (walls, ground, objects) that produce non-zero Laplacian variance. Fix: use real footage for validation.
