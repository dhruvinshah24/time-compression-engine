"""
Progressive Scaling Benchmark — Phase 4 Exp-G.

Measures how TCE pipeline processing time scales with video duration.
Tests: 30s, 60s, 5min (if available), 10min (if available), 30min (if available).

Does NOT run YOLO detection (too slow for 30min synthetic video without real content).
Instead measures the pipeline stages that DO scale with duration:
  - S02: frame extraction time
  - Adaptive skip analysis time
  - Quality analysis time
  - Total pipeline wall time

Output:
  reports/scaling-benchmark.md
  results/TCE-v1.0/scaling-benchmark.json
"""

import json
import sys
import time
from pathlib import Path

import cv2

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

SCALING_VIDEOS = [
    ("scaling_30s",   REPO_ROOT / "data/real/synthetic/scaling/scaling_30s.mp4",   30),
    ("scaling_60s",   REPO_ROOT / "data/real/synthetic/scaling/scaling_60s.mp4",   60),
    ("scaling_5min",  REPO_ROOT / "data/real/synthetic/scaling/scaling_5min.mp4",  300),
    ("scaling_10min", REPO_ROOT / "data/real/synthetic/scaling/scaling_10min.mp4", 600),
    ("scaling_30min", REPO_ROOT / "data/real/synthetic/scaling/scaling_30min.mp4", 1800),
]

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _get_video_info(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps    = cap.get(cv2.CAP_PROP_FPS)
    w      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return {"frames": frames, "fps": fps, "width": w, "height": h}


def measure_extraction_time(video_path: str, skip_rate: int = 5) -> dict:
    """Measure how long it takes to extract frames with FFmpeg at a fixed skip rate."""
    import subprocess
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as tmpdir:
        ffmpeg_path = "ffmpeg"
        cmd = [
            ffmpeg_path, "-i", video_path,
            "-vf", f"select='not(mod(n\\,{skip_rate}))'",
            "-vsync", "vfr",
            "-q:v", "5",
            f"{tmpdir}/frame_%08d.jpg",
            "-loglevel", "error",
        ]
        t0 = time.perf_counter()
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        elapsed = time.perf_counter() - t0
        frames_written = len([f for f in os.listdir(tmpdir) if f.endswith(".jpg")])
        return {
            "extraction_time_s": round(elapsed, 2),
            "frames_extracted":  frames_written,
            "ffmpeg_returncode": result.returncode,
        }


def measure_adaptive_skip_time(video_path: str) -> dict:
    """Measure adaptive skip pre-analysis time."""
    from app.utils.adaptive_skip import AdaptiveSkipConfig, select_frames_for_extraction

    cfg = AdaptiveSkipConfig(enabled=True)
    t0 = time.perf_counter()
    try:
        indices, stats = select_frames_for_extraction(video_path, config=cfg)
        elapsed = time.perf_counter() - t0
        return {
            "adaptive_skip_time_s": round(elapsed, 2),
            "frames_selected":      len(indices),
            "effective_ratio":      stats.effective_sampling_ratio,
            "status":               "completed",
        }
    except Exception as exc:
        return {
            "adaptive_skip_time_s": round(time.perf_counter() - t0, 2),
            "status":               "error",
            "error":                str(exc),
        }


def measure_quality_analysis_time(video_path: str, sample_rate: int = 10) -> dict:
    """Measure how long quality analysis takes (sampled every Nth frame)."""
    from app.utils.quality_analyzer import analyze_frame, QualityThresholds
    import numpy as np

    thresholds = QualityThresholds()
    cap = cv2.VideoCapture(video_path)
    frames_analyzed = 0
    t0 = time.perf_counter()

    i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if i % sample_rate == 0:
            analyze_frame(frame, frame_number=i, timestamp_ms=i * 40.0, thresholds=thresholds)
            frames_analyzed += 1
        i += 1

    cap.release()
    elapsed = time.perf_counter() - t0
    return {
        "quality_analysis_time_s": round(elapsed, 2),
        "frames_analyzed":         frames_analyzed,
        "ms_per_frame":            round(elapsed * 1000 / max(frames_analyzed, 1), 1),
    }


def main():
    import psutil

    print("Progressive Scaling Benchmark — Phase 4 Exp-G")
    results = []

    for vid_id, vid_path, expected_dur in SCALING_VIDEOS:
        if not vid_path.exists():
            print(f"  MISSING: {vid_path.name} — skipped")
            results.append({"video_id": vid_id, "status": "not_found", "expected_duration_s": expected_dur})
            continue

        info = _get_video_info(str(vid_path))
        file_mb = vid_path.stat().st_size / (1024 * 1024)
        print(f"\n{vid_id}  ({info['frames']} frames, {file_mb:.1f}MB)")

        mem_before = psutil.virtual_memory().used // (1024 * 1024)

        t_total = time.perf_counter()

        extraction = measure_extraction_time(str(vid_path), skip_rate=5)
        adaptive   = measure_adaptive_skip_time(str(vid_path))
        quality    = measure_quality_analysis_time(str(vid_path))

        total_elapsed = time.perf_counter() - t_total
        mem_after = psutil.virtual_memory().used // (1024 * 1024)

        result = {
            "video_id":             vid_id,
            "status":               "completed",
            "expected_duration_s":  expected_dur,
            "actual_duration_s":    round(info["frames"] / max(info["fps"], 1), 1),
            "file_size_mb":         round(file_mb, 1),
            "video_info":           info,
            "extraction":           extraction,
            "adaptive_skip":        adaptive,
            "quality_analysis":     quality,
            "total_analysis_time_s": round(total_elapsed, 2),
            "real_time_factor":     round(total_elapsed / max(expected_dur, 1), 3),
            "ram_delta_mb":         mem_after - mem_before,
        }
        results.append(result)

        rtf = result["real_time_factor"]
        print(f"  Extraction: {extraction['extraction_time_s']}s  frames={extraction['frames_extracted']}")
        print(f"  Adaptive skip: {adaptive.get('adaptive_skip_time_s')}s  selected={adaptive.get('frames_selected')}")
        print(f"  Quality analysis: {quality['quality_analysis_time_s']}s  ({quality['ms_per_frame']}ms/frame)")
        print(f"  Total: {total_elapsed:.1f}s  RTF: {rtf:.3f}x  RAM delta: {mem_after - mem_before}MB")

    # Save JSON
    out_json = RESULTS_DIR / "scaling-benchmark.json"
    with open(out_json, "w") as f:
        json.dump({
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "results": results,
        }, f, indent=2, default=str)

    # Write markdown
    md_path = REPORTS_DIR / "scaling-benchmark.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Scaling Benchmark — Phase 4 Exp-G\n\n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n\n")
        f.write("> **Note:** YOLO detection NOT included in scaling test.\n")
        f.write("> These times measure extraction, adaptive skip analysis, and quality analysis.\n")
        f.write("> Full pipeline scaling (with detection) takes significantly longer.\n\n")

        f.write("## Processing Time vs Video Duration\n\n")
        f.write("| Video | Duration | File | Extraction | Adaptive Skip | Quality | Total | RTF |\n")
        f.write("|---|---|---|---|---|---|---|---|\n")
        for r in results:
            if r.get("status") != "completed":
                f.write(f"| {r['video_id']} | {r['expected_duration_s']}s | - | NOT FOUND | - | - | - | - |\n")
                continue
            e = r.get("extraction", {})
            a = r.get("adaptive_skip", {})
            q = r.get("quality_analysis", {})
            f.write(
                f"| {r['video_id']} "
                f"| {r['actual_duration_s']}s "
                f"| {r['file_size_mb']}MB "
                f"| {e.get('extraction_time_s')}s "
                f"| {a.get('adaptive_skip_time_s')}s "
                f"| {q.get('quality_analysis_time_s')}s "
                f"| {r['total_analysis_time_s']}s "
                f"| {r['real_time_factor']}x |\n"
            )

        f.write("\n## Observations\n\n")
        completed = [r for r in results if r.get("status") == "completed"]
        if len(completed) >= 2:
            first, last = completed[0], completed[-1]
            time_ratio = last["total_analysis_time_s"] / max(first["total_analysis_time_s"], 0.001)
            dur_ratio  = last["expected_duration_s"] / max(first["expected_duration_s"], 1)
            f.write(f"- Duration increased {dur_ratio:.1f}x ({first['expected_duration_s']}s → {last['expected_duration_s']}s)\n")
            f.write(f"- Processing time increased {time_ratio:.1f}x — ")
            if time_ratio < dur_ratio * 1.2:
                f.write("**near-linear scaling** (within 20% of linear).\n")
            else:
                f.write(f"**super-linear** ({time_ratio:.1f}x vs expected {dur_ratio:.1f}x). Investigate.\n")

        f.write("\n## Capability Classification\n\n")
        f.write("| Capability | Classification |\n")
        f.write("|---|---|\n")
        if any(r.get("status") == "completed" for r in results):
            f.write("| Frame extraction scaling | **PARTIALLY VALIDATED** (synthetic video) |\n")
            f.write("| Adaptive skip scaling | **PARTIALLY VALIDATED** (synthetic video) |\n")
            f.write("| Quality analysis scaling | **PARTIALLY VALIDATED** (synthetic video) |\n")
        f.write("| Full pipeline (with detection) scaling | **NOT YET VALIDATED** |\n")
        f.write("| 24-hour processing stability | **NOT YET VALIDATED** |\n")

    print(f"\nResults: {out_json}")
    print(f"Report:  {md_path}")


if __name__ == "__main__":
    main()
