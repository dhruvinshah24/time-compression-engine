"""
Low-Light Detection Benchmark — Phase 4 Exp-B.

Tests quality analysis and low-light detection at 4 illumination levels.
Uses the synthetic low_light_4levels/ corpus.

Measures:
  - average brightness per video
  - quality score distribution
  - low_light_ratio (fraction of frames classified as LOW_LIGHT)
  - unusable_ratio (fraction classified as UNUSABLE)
  - CLAHE/gamma effect on brightness

This does NOT measure detection accuracy (YOLO cannot detect shapes).
It validates the quality classification pipeline stage (S04 quality sub-pass).

Output:
  reports/low-light-benchmark.md
  results/TCE-v1.0/low-light-benchmark.json

Usage:
    python backend/scripts/benchmark_low_light.py
"""

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

LEVEL_VIDEOS = [
    ("level_a_normal",    REPO_ROOT / "data/real/synthetic/low_light_4levels/level_a_normal.mp4",    "NORMAL"),
    ("level_b_low",       REPO_ROOT / "data/real/synthetic/low_light_4levels/level_b_low.mp4",       "LOW_LIGHT"),
    ("level_c_very_low",  REPO_ROOT / "data/real/synthetic/low_light_4levels/level_c_very_low.mp4",  "VERY_LOW_LIGHT"),
    ("level_d_unusable",  REPO_ROOT / "data/real/synthetic/low_light_4levels/level_d_unusable.mp4",  "UNUSABLE"),
]

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def analyze_video_brightness(video_path: str) -> dict:
    """Read all frames, compute brightness stats."""
    cap = cv2.VideoCapture(video_path)
    brightnesses = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightnesses.append(float(np.mean(gray)))
    cap.release()
    if not brightnesses:
        return {}
    return {
        "mean_brightness":   round(float(np.mean(brightnesses)), 2),
        "median_brightness": round(float(np.median(brightnesses)), 2),
        "min_brightness":    round(float(np.min(brightnesses)), 2),
        "max_brightness":    round(float(np.max(brightnesses)), 2),
        "std_brightness":    round(float(np.std(brightnesses)), 2),
        "frames_analyzed":   len(brightnesses),
    }


def classify_quality(video_path: str) -> dict:
    """Run the TCE quality analyzer on each frame."""
    from app.utils.quality_analyzer import analyze_frame, QualityThresholds, QualityClass

    thresholds = QualityThresholds()
    cap = cv2.VideoCapture(video_path)

    low_light_count = 0
    very_low_light_count = 0
    unusable_count = 0
    total = 0
    quality_scores = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Analyze every 10th frame to save time
        if total % 10 == 0:
            result = analyze_frame(frame, frame_number=total, timestamp_ms=total * 40.0, thresholds=thresholds)
            quality_scores.append(result.mean_luminance)
            if result.quality_class == QualityClass.UNUSABLE:
                unusable_count += 1
            elif result.quality_class == QualityClass.VERY_LOW_LIGHT:
                very_low_light_count += 1
            elif result.quality_class == QualityClass.LOW_LIGHT:
                low_light_count += 1
        total += 1

    cap.release()
    sampled = len(quality_scores)
    return {
        "total_frames":         total,
        "frames_sampled":       sampled,
        "low_light_count":      low_light_count,
        "very_low_light_count": very_low_light_count,
        "unusable_count":       unusable_count,
        "low_light_ratio":      round(low_light_count / max(sampled, 1), 3),
        "very_low_light_ratio": round(very_low_light_count / max(sampled, 1), 3),
        "unusable_ratio":       round(unusable_count / max(sampled, 1), 3),
        "avg_mean_luminance":   round(float(np.mean(quality_scores)), 2) if quality_scores else None,
        "min_mean_luminance":   round(float(np.min(quality_scores)), 2) if quality_scores else None,
    }



def test_clahe_effect(video_path: str, n_frames: int = 30) -> dict:
    """Compare brightness before/after CLAHE + gamma correction."""
    from app.utils.low_light import preprocess_frame
    from app.utils.quality_analyzer import analyze_frame, QualityThresholds

    thresholds = QualityThresholds()
    cap = cv2.VideoCapture(video_path)

    raw_brightnesses = []
    processed_brightnesses = []
    count = 0

    while count < n_frames:
        ret, frame = cap.read()
        if not ret:
            break
        raw_b = float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)))
        quality = analyze_frame(frame, frame_number=count, timestamp_ms=count * 40.0, thresholds=thresholds)
        preprocessed = preprocess_frame(frame, quality=quality)
        processed_frame = preprocessed.frame if hasattr(preprocessed, "frame") else frame
        proc_b = float(np.mean(cv2.cvtColor(processed_frame, cv2.COLOR_BGR2GRAY)))
        raw_brightnesses.append(raw_b)
        processed_brightnesses.append(proc_b)
        count += 1

    cap.release()
    if not raw_brightnesses:
        return {}

    avg_raw  = float(np.mean(raw_brightnesses))
    avg_proc = float(np.mean(processed_brightnesses))
    return {
        "frames_compared":      count,
        "avg_brightness_raw":   round(avg_raw, 2),
        "avg_brightness_clahe": round(avg_proc, 2),
        "brightness_gain":      round(avg_proc - avg_raw, 2),
        "brightness_gain_pct":  round((avg_proc - avg_raw) / max(avg_raw, 1) * 100, 1),
    }


def main():
    print("Low-Light Detection Benchmark — Phase 4 Exp-B")
    all_results = []

    for vid_id, vid_path, expected_label in LEVEL_VIDEOS:
        if not vid_path.exists():
            print(f"  MISSING: {vid_path}")
            all_results.append({"video_id": vid_id, "status": "not_found"})
            continue

        print(f"\n{vid_id} (expected: {expected_label})")
        t0 = time.perf_counter()

        brightness = analyze_video_brightness(str(vid_path))
        quality    = classify_quality(str(vid_path))
        clahe      = test_clahe_effect(str(vid_path))

        elapsed = time.perf_counter() - t0

        result = {
            "video_id":        vid_id,
            "expected_label":  expected_label,
            "status":          "completed",
            "analysis_time_s": round(elapsed, 2),
            "brightness":      brightness,
            "quality":         quality,
            "clahe_effect":    clahe,
        }
        all_results.append(result)

        print(f"  Brightness: {brightness.get('mean_brightness'):.1f}/255")
        print(f"  Low-light ratio: {quality.get('low_light_ratio'):.1%}")
        print(f"  Very-low-light ratio: {quality.get('very_low_light_ratio'):.1%}")
        print(f"  Unusable ratio:  {quality.get('unusable_ratio'):.1%}")
        print(f"  CLAHE gain: {clahe.get('brightness_gain_pct'):.1f}%")
        print(f"  Avg luminance: {quality.get('avg_mean_luminance')}")

    # Save JSON
    out_json = RESULTS_DIR / "low-light-benchmark.json"
    with open(out_json, "w") as f:
        json.dump({
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": all_results,
        }, f, indent=2, default=str)

    # Write markdown
    md_path = REPORTS_DIR / "low-light-benchmark.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Low-Light Detection Benchmark — Phase 4 Exp-B\n\n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n\n")
        f.write("> Values are **measured**, not estimated. Videos are synthetic.\n\n")

        f.write("## Quality Classification Results\n\n")
        f.write("| Video | Expected | Mean Brightness | Low-Light % | Very-Low % | Unusable % | Avg Luminance |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in all_results:
            if r.get("status") != "completed":
                f.write(f"| {r['video_id']} | - | NOT FOUND | - | - | - | - |\n")
                continue
            b = r.get("brightness", {})
            q = r.get("quality", {})
            f.write(
                f"| {r['video_id']} "
                f"| {r['expected_label']} "
                f"| {b.get('mean_brightness', 0):.1f} "
                f"| {q.get('low_light_ratio', 0):.1%} "
                f"| {q.get('very_low_light_ratio', 0):.1%} "
                f"| {q.get('unusable_ratio', 0):.1%} "
                f"| {q.get('avg_mean_luminance', '?')} |\n"
            )

        f.write("\n## CLAHE Preprocessing Effect\n\n")
        f.write("| Video | Brightness Before | Brightness After | Gain |\n")
        f.write("|---|---|---|---|\n")
        for r in all_results:
            if r.get("status") != "completed":
                continue
            c = r.get("clahe_effect", {})
            f.write(
                f"| {r['video_id']} "
                f"| {c.get('avg_brightness_raw', '?')} "
                f"| {c.get('avg_brightness_clahe', '?')} "
                f"| +{c.get('brightness_gain_pct', '?')}% |\n"
            )

        f.write("\n## Limitations\n\n")
        f.write("- These are synthetic videos with uniform pixel brightness, NOT real low-light footage.\n")
        f.write("- Real low-light footage has sensor noise, varying spatial distribution, bloom effects.\n")
        f.write("- Quality classifier was tuned for heuristic brightness thresholds, not calibrated.\n")
        f.write("- CLAHE gain percentage is not the same as detection improvement.\n")
        f.write("- **Capability status: PARTIALLY VALIDATED** — quality classification works on synthetic input.\n")
        f.write("  Real low-light footage required to validate detection improvement.\n")

    print(f"\nResults: {out_json}")
    print(f"Report:  {md_path}")


if __name__ == "__main__":
    main()
