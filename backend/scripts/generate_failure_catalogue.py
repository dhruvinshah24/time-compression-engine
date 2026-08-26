"""
Generate Phase 4 failure catalogue from observed experiment results.

Run this AFTER all Phase 4 benchmarks have been executed.
Records every confirmed failure as structured data.

Output:
    reports/failures/catalogue-phase4.json
    reports/failures/FAIL-*.md (for CRITICAL/MAJOR items)
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.utils.failure_catalogue import FailureCatalogue


def main():
    cat = FailureCatalogue()

    # FAIL-001: Quality classifier classifies all synthetic frames as UNUSABLE
    cat.add(
        video_id="all_low_light_levels",
        category="VALIDATOR_WARNING",
        severity="MAJOR",
        description=(
            "Quality classifier classifies ALL synthetic frames as UNUSABLE "
            "regardless of brightness level (78.8/255 → UNUSABLE, 33.5/255 → UNUSABLE, "
            "10.8/255 → UNUSABLE, 2.8/255 → UNUSABLE). "
            "Root cause: Laplacian blur score is near-zero for solid-color synthetic frames. "
            "The unusable_blur_score threshold (15.0) fires on every frame. "
            "This is classifier-correct behaviour on synthetic input but means "
            "quality classification cannot be validated using these test videos."
        ),
        stage="s04_object_detect",
        expected="level_a_normal → NORMAL, level_b_low → LOW_LIGHT, level_c_very_low → VERY_LOW_LIGHT",
        actual="All 4 levels → UNUSABLE (0% LOW_LIGHT, 0% VERY_LOW_LIGHT, 100% UNUSABLE)",
        possible_cause=(
            "Laplacian variance on solid-color frames ≈ 0. "
            "The QualityThresholds.unusable_blur_score=15.0 threshold triggers. "
            "Real surveillance frames have texture (walls, ground, objects) that "
            "produce non-zero Laplacian variance. Fix: use real footage for validation."
        ),
        benchmark_file="results/TCE-v1.0/low-light-benchmark.json",
    )

    # FAIL-002: ROI cold-start bug
    cat.add(
        video_id="exp_e_roi_crossing",
        category="MISSED_EVENT",
        severity="CRITICAL",
        description=(
            "When a track's first observation is inside a restricted zone, no "
            "restricted_zone_entry event is emitted. The ROIManager.check_point() "
            "method silently records the initial state without generating an event. "
            "This means any person who is ALREADY in a restricted area when the "
            "camera starts recording will never trigger an entry alert."
        ),
        stage="s07_event_understand",
        timestamp_s=0.0,
        expected="restricted_zone_entry event at frame 0 when track starts inside zone",
        actual="0 events generated (no transition detected, only initial state recorded)",
        possible_cause=(
            "ROIManager._membership[track_id][zone_id] is None on first observation. "
            "Code silently assigned the state: "
            "`if was_inside is None: self._membership[...] = inside_now; continue` "
            "without emitting any event. "
            "Fixed in Phase 4: now emits entry event immediately with evidence={'cold_start': True}."
        ),
        benchmark_file="results/TCE-v1.0/roi-validation.json",
    )

    # FAIL-003: ROI entry not detected in corpus video simulation
    cat.add(
        video_id="exp_e_roi_crossing",
        category="MISSED_EVENT",
        severity="MAJOR",
        description=(
            "In the corpus video trajectory simulation, the rectangle entered "
            "the zone at ~t=14.3s but no restricted_zone_entry event was generated. "
            "An exit event was detected at t=18.36s (expected at t=25.7s — "
            "timing error of 7.34s). "
            "Note: this failure is partially explained by FAIL-002 (cold-start bug). "
            "The cold-start fix may resolve the entry detection issue."
        ),
        stage="s07_event_understand",
        timestamp_s=14.3,
        expected="entry event at ~t=14.3s, exit event at ~t=25.7s",
        actual="0 entry events, 1 exit event at t=18.36s (7.34s error)",
        possible_cause=(
            "The ROI cold-start bug (FAIL-002) is the primary cause. "
            "The synthetic track starts outside the zone, so the cold-start bug "
            "doesn't apply directly. "
            "There may be a second issue: the zone boundary check fires inconsistently. "
            "The exit at 18.36s (instead of 25.7s) suggests the zone boundary "
            "polygon may have floating-point precision issues at the edge."
        ),
        benchmark_file="results/TCE-v1.0/roi-validation.json",
    )

    # FAIL-004: YOLO11m false positives on synthetic video
    cat.add(
        video_id="exp_a_normal_walking",
        category="FALSE_EVENT",
        severity="MINOR",
        description=(
            "YOLO11m detected 23 'tv' class objects across 100 frames of a synthetic "
            "video containing only a white rectangle on a gray background. "
            "YOLO11n, yolo11l, and yolo11x detected 0 objects on the same video. "
            "This is not a pipeline failure — YOLO models are not designed for "
            "synthetic input. But it demonstrates that YOLO11m has higher false "
            "positive rates on rectangular shapes that pattern-match COCO class 63 (tv)."
        ),
        stage="s04_object_detect",
        expected="0 detections on synthetic geometric shapes",
        actual="23 'tv' detections across 100 frames (avg 0.23/frame)",
        possible_cause=(
            "YOLO11m confidence threshold (0.25) is low enough to trigger on "
            "rectangular shapes that partially match COCO 'tv' feature patterns. "
            "At conf=0.5 this might not occur. Not a critical issue for real footage."
        ),
        benchmark_file="reports/model-comparison-raw.json",
    )

    # FAIL-005: Adaptive skip under-sampling during motion burst
    cat.add(
        video_id="exp_c_fast_motion",
        category="COMPRESSION_ERROR",
        severity="MAJOR",
        description=(
            "On fast_motion_60s.mp4 (60s, burst at t=20-30s), adaptive skip "
            "selected only 174 frames (11.6% ratio) vs fixed-5 which selected "
            "300 frames (20% ratio). Within the motion burst region (frames 500-750), "
            "adaptive retained 16.3% of frames vs 20.3% for fixed-5. "
            "This means adaptive skip MISSED MORE CRITICAL FRAMES than fixed-5 "
            "during the most important part of the video."
        ),
        stage="s02_extract",
        expected="Adaptive skip should retain MORE frames during motion burst than fixed-5",
        actual="Adaptive retained 16.3% of burst frames; fixed-5 retained 20.3%",
        possible_cause=(
            "MOG2 warmup (25 frames default) means the first 1 second of motion "
            "is not well-detected. The protection_threshold (0.08) may be too "
            "high for synthetic motion. Additionally, the adaptive selection "
            "overhead was 14.9 seconds — 25% of the 60s video duration."
        ),
        benchmark_file="results/TCE-v1.0/adaptive-skip-comparison.json",
    )

    out_dir = Path(__file__).parent.parent.parent / "reports" / "failures"
    path = cat.save(out_dir, run_id="phase4")
    stats = cat.statistics()

    print(f"Failure catalogue written to: {path}")
    print(f"Total failures: {stats['total']}")
    print(f"By category: {stats['failure_count_by_category']}")
    print(f"By severity: {stats['failure_count_by_severity']}")
    print(f"Most implicated stage: {stats['most_implicated_stage']}")

    for rec in cat.failures:
        sev_marker = "!!" if rec.severity == "CRITICAL" else "!" if rec.severity == "MAJOR" else " "
        print(f"  {sev_marker} {rec.failure_id}: [{rec.severity}] {rec.category} — {rec.description[:80]}...")


if __name__ == "__main__":
    main()
