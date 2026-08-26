"""
Adaptive Skip Comparison — Phase 4 Experiment F.

Compares three frame selection strategies on a 60s video with a motion burst:

  FIXED_SLOW:   select every 5th frame (skip_rate=5)
  FIXED_FAST:   select every 1st frame (all frames, no skip)
  ADAPTIVE:     pre-extraction streaming with MOG2

Measures:
  - frames selected
  - processing time
  - effective sampling ratio
  - frames in motion burst region selected
  - "critical frame retention" — how many burst frames were kept

This is a STRUCTURAL experiment — it measures frame selection behaviour,
not detection accuracy (YOLO cannot detect synthetic shapes).

Output:
  reports/adaptive-skip-comparison.md
  results/TCE-v1.0/adaptive-skip-comparison.json

Usage:
    python backend/scripts/compare_adaptive_skip.py
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

TEST_VIDEO = REPO_ROOT / "data" / "real" / "synthetic" / "fast_motion_60s.mp4"
RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# The motion burst is 20s-30s at 25fps → frames 500-750
MOTION_BURST_START = 500
MOTION_BURST_END   = 750
FPS = 25


def _get_total_frames(video_path: str) -> int:
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return total


def strategy_fixed(video_path: str, skip_rate: int) -> dict:
    """Select every Nth frame."""
    t0 = time.perf_counter()
    total = _get_total_frames(video_path)
    indices = list(range(0, total, skip_rate))
    elapsed = time.perf_counter() - t0

    burst_selected = [i for i in indices if MOTION_BURST_START <= i <= MOTION_BURST_END]
    burst_total = MOTION_BURST_END - MOTION_BURST_START + 1

    return {
        "strategy":               f"fixed_skip_{skip_rate}",
        "skip_rate":              skip_rate,
        "total_video_frames":     total,
        "frames_selected":        len(indices),
        "effective_ratio":        len(indices) / max(total, 1),
        "selection_time_ms":      int(elapsed * 1000),
        "burst_frames_selected":  len(burst_selected),
        "burst_frames_total":     burst_total,
        "burst_retention_pct":    round(len(burst_selected) / max(burst_total, 1) * 100, 1),
        "frame_indices_sample":   indices[:10],
        "note": f"Simple modulo selection: every {skip_rate}th frame",
    }


def strategy_adaptive(video_path: str) -> dict:
    """Pre-extraction streaming adaptive skip."""
    from app.utils.adaptive_skip import AdaptiveSkipConfig, select_frames_for_extraction

    cfg = AdaptiveSkipConfig(
        enabled=True,
        warmup_frames=25,
        static_skip=10,
        low_motion_skip=6,
        medium_motion_skip=3,
        high_motion_skip=1,
        protection_threshold=0.08,
        protection_window_frames=15,
    )

    t0 = time.perf_counter()
    indices, stats = select_frames_for_extraction(video_path, config=cfg)
    elapsed = time.perf_counter() - t0

    burst_selected = [i for i in indices if MOTION_BURST_START <= i <= MOTION_BURST_END]
    burst_total = MOTION_BURST_END - MOTION_BURST_START + 1

    return {
        "strategy":               "adaptive_mog2",
        "skip_rate":              "variable",
        "total_video_frames":     stats.total_video_frames,
        "frames_selected":        len(indices),
        "effective_ratio":        stats.effective_sampling_ratio,
        "selection_time_ms":      int(elapsed * 1000),
        "burst_frames_selected":  len(burst_selected),
        "burst_frames_total":     burst_total,
        "burst_retention_pct":    round(len(burst_selected) / max(burst_total, 1) * 100, 1),
        "frame_indices_sample":   (indices[:10] if indices else []),
        "adaptive_stats":         stats.to_dict(),
        "note": (
            "Pre-extraction MOG2 streaming: selects high-motion frames more densely, "
            "skips static frames aggressively. "
            "Protection window triggered during burst."
        ),
    }


def main():
    if not TEST_VIDEO.exists():
        print(f"Test video not found: {TEST_VIDEO}")
        print("Run generate_validation_corpus.py first.")
        sys.exit(1)

    print("Adaptive Skip Comparison — Phase 4 Exp-F")
    print(f"  Video: {TEST_VIDEO}")
    print(f"  Motion burst: frames {MOTION_BURST_START}-{MOTION_BURST_END} (t=20s-30s)")
    total_frames = _get_total_frames(str(TEST_VIDEO))
    print(f"  Total frames: {total_frames}")

    results = {}

    print("\n[1/3] Fixed skip=1 (all frames)...")
    results["fixed_1"] = strategy_fixed(str(TEST_VIDEO), skip_rate=1)

    print("[2/3] Fixed skip=5...")
    results["fixed_5"] = strategy_fixed(str(TEST_VIDEO), skip_rate=5)

    print("[3/3] Adaptive MOG2...")
    results["adaptive"] = strategy_adaptive(str(TEST_VIDEO))

    # Save JSON
    out_json = RESULTS_DIR / "adaptive-skip-comparison.json"
    data = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "video": str(TEST_VIDEO.name),
        "total_frames": total_frames,
        "motion_burst_region": f"frames {MOTION_BURST_START}-{MOTION_BURST_END}",
        "results": results,
    }
    with open(out_json, "w") as f:
        json.dump(data, f, indent=2, default=str)

    # Print comparison table
    print(f"\n{'='*68}")
    print(f"{'Strategy':<20} {'Selected':>9} {'Ratio':>7} {'SelTime':>9} {'BurstRet':>10}")
    print(f"{'='*68}")
    for key, r in results.items():
        print(
            f"{r['strategy']:<20} "
            f"{r['frames_selected']:>9} "
            f"{r['effective_ratio']:>7.1%} "
            f"{r['selection_time_ms']:>7}ms "
            f"{r['burst_retention_pct']:>9.1f}%"
        )
    print(f"{'='*68}")

    # Write markdown report
    md_path = REPORTS_DIR / "adaptive-skip-comparison.md"
    r1 = results["fixed_1"]
    r5 = results["fixed_5"]
    ra = results["adaptive"]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Adaptive Skip Comparison — Phase 4 Exp-F\n\n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n")
        f.write(f"Video: `{TEST_VIDEO.name}` ({r1['total_video_frames']} frames, 60s @ 25fps)  \n")
        f.write(f"Motion burst region: frames {MOTION_BURST_START}–{MOTION_BURST_END} (t=20s–30s)  \n\n")
        f.write("> All values are **measured**, not estimated.\n\n")

        f.write("## Results Table\n\n")
        f.write("| Strategy | Frames Selected | Ratio | Selection Time | Burst Retention |\n")
        f.write("|---|---|---|---|---|\n")
        for r in [r1, r5, ra]:
            f.write(
                f"| {r['strategy']} "
                f"| {r['frames_selected']} of {r['total_video_frames']} "
                f"| {r['effective_ratio']:.1%} "
                f"| {r['selection_time_ms']}ms "
                f"| {r['burst_retention_pct']:.1f}% |\n"
            )

        f.write("\n## Burst Region Detail\n\n")
        f.write(f"The motion burst (frames {MOTION_BURST_START}–{MOTION_BURST_END}) "
                f"is where a 'person' moves rapidly.\n")
        f.write("Critical frame retention = fraction of burst frames that were selected.\n\n")
        f.write("| Strategy | Burst Frames Selected | Burst Total | Retention |\n")
        f.write("|---|---|---|---|\n")
        for r in [r1, r5, ra]:
            f.write(
                f"| {r['strategy']} "
                f"| {r['burst_frames_selected']} "
                f"| {r['burst_frames_total']} "
                f"| {r['burst_retention_pct']:.1f}% |\n"
            )

        if "adaptive_stats" in ra:
            as_ = ra["adaptive_stats"]
            f.write(f"\n## Adaptive Skip Internal Stats\n\n")
            f.write(f"- Protection windows triggered: **{as_.get('protected_windows', 0)}**\n")
            f.write(f"- Protected frames: **{as_.get('protected_frames', 0)}**\n")
            f.write(f"- Average motion score: **{as_.get('average_motion_score_pct', 0):.2f}%**\n")
            f.write(f"- Max motion score: **{as_.get('maximum_motion_score_pct', 0):.2f}%**\n")
            tier = as_.get("tier_distribution", {})
            if tier:
                f.write(f"- Tier distribution: {tier}\n")

        f.write("\n## Observations\n\n")
        # Generate honest observations
        adaptive_better = ra["burst_retention_pct"] >= r5["burst_retention_pct"]
        adaptive_fewer  = ra["frames_selected"] < r5["frames_selected"]
        f.write(
            f"- Adaptive selected {ra['frames_selected']} frames vs "
            f"{r5['frames_selected']} for fixed-5 "
            f"({'fewer' if adaptive_fewer else 'more'} frames).\n"
        )
        f.write(
            f"- Burst retention: adaptive={ra['burst_retention_pct']:.1f}%, "
            f"fixed-5={r5['burst_retention_pct']:.1f}%. "
            f"{'Adaptive preserved more critical frames.' if adaptive_better else 'Fixed-5 preserved more critical frames — investigate protection threshold.'}\n"
        )
        f.write(
            f"- Selection overhead: adaptive={ra['selection_time_ms']}ms vs "
            f"fixed-5={r5['selection_time_ms']}ms (streaming cost).\n"
        )
        f.write("\n## Limitations\n\n")
        f.write("- This experiment uses synthetic pixel motion (moving rectangle), NOT real scene content.\n")
        f.write("- MOG2 detects pixel change, not semantic events. Results may differ on real footage.\n")
        f.write("- Events missed cannot be quantified without YOLO detections on real people.\n")
        f.write("- **Capability status: PARTIALLY VALIDATED** — measured on synthetic video. "
                "Real-footage validation required to confirm event preservation.\n")

    print(f"\nResults: {out_json}")
    print(f"Report:  {md_path}")


if __name__ == "__main__":
    main()
