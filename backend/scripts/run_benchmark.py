"""
Phase 4 Benchmark Runner — Time Compression Engine v1.0.1

Runs the TCE pipeline on each video in the validation corpus and records
structured results in results/TCE-v1.0/benchmark-NNN.json.

Every benchmark record is honest:
- Only measured values are recorded
- Null = data not available, not a placeholder
- No ground truth precision/recall unless annotation file exists
- YOLO detection of synthetic shapes is explicitly noted as expected zero

Usage:
    python backend/scripts/run_benchmark.py [--video VIDEO_ID] [--all]

Arguments:
    --all                Run all videos in data/real/synthetic/manifest.json
    --video VIDEO_ID     Run only this video_id
    --profile PROFILE    Model profile: fast, balanced, accuracy (default: accuracy)
    --skip SKIP_RATE     Fixed frame skip rate (default: 5)
    --adaptive           Enable adaptive frame skip (default: off)
    --output-dir DIR     Results directory (default: results/TCE-v1.0/)

The runner does NOT start the FastAPI server. It drives the pipeline
stages directly to avoid HTTP overhead and server state.

Exit codes:
    0 = all benchmarks completed (may still have per-video failures)
    1 = fatal configuration or import error
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

# Ensure backend/ is on path
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

REPO_ROOT = BACKEND_DIR.parent
RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
CORPUS_DIR = REPO_ROOT / "data" / "real" / "synthetic"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _gpu_info() -> dict:
    try:
        import torch
        if torch.cuda.is_available():
            dev = torch.cuda.get_device_properties(0)
            return {
                "name":       dev.name,
                "vram_mb":    dev.total_memory // (1024 * 1024),
                "cuda":       torch.version.cuda,
                "available":  True,
            }
    except Exception:
        pass
    return {"available": False}


def _ram_mb() -> int:
    try:
        import psutil
        return psutil.virtual_memory().total // (1024 * 1024)
    except Exception:
        return 0


def _next_benchmark_num() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(RESULTS_DIR.glob("benchmark-*.json"))
    if not existing:
        return 1
    last = int(existing[-1].stem.split("-")[-1])
    return last + 1


async def _run_pipeline(video_path: str, settings: dict, job_id: str) -> dict:
    """
    Run the TCE pipeline stages directly (no HTTP).
    Returns a dict with stage results and timing.
    """
    from app.pipeline.context import PipelineContext
    from app.pipeline.stages import (
        s01_upload, s02_extract, s03_scene_detect, s04_object_detect,
        s05_track, s06_motion_analyze, s07_event_understand,
        s08_confidence_fuse, s09_story_build, s10_rank,
        s11_summarize, s12_export,
    )

    STAGES = [
        ("s01_upload",         s01_upload),
        ("s02_extract",        s02_extract),
        ("s03_scene_detect",   s03_scene_detect),
        ("s04_object_detect",  s04_object_detect),
        ("s05_track",          s05_track),
        ("s06_motion_analyze", s06_motion_analyze),
        ("s07_event_understand", s07_event_understand),
        ("s08_confidence_fuse", s08_confidence_fuse),
        ("s09_story_build",    s09_story_build),
        ("s10_rank",           s10_rank),
        ("s11_summarize",      s11_summarize),
        ("s12_export",         s12_export),
    ]

    ctx = PipelineContext(
        job_id=job_id,
        video_path=video_path,
        settings=settings,
    )

    stage_results = []
    pipeline_start = time.perf_counter()

    for stage_name, stage_mod in STAGES:
        t0 = time.perf_counter()
        try:
            result = await stage_mod.run(ctx)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            stage_results.append({
                "name":        stage_name,
                "status":      "completed" if result.success else "failed",
                "duration_ms": result.duration_ms or elapsed_ms,
                "metrics":     result.metrics or {},
                "warnings":    result.warnings or [],
                "errors":      result.errors or [],
                "logs":        (result.logs or [])[-5:],  # last 5 log lines only
            })
            if not result.success:
                print(f"    ✗ {stage_name} FAILED: {result.errors}")
                break
            else:
                print(f"    ✓ {stage_name}  {result.duration_ms}ms")
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            stage_results.append({
                "name":        stage_name,
                "status":      "exception",
                "duration_ms": elapsed_ms,
                "metrics":     {},
                "warnings":    [],
                "errors":      [str(exc)],
                "logs":        [traceback.format_exc()[:500]],
            })
            print(f"    ✗ {stage_name} EXCEPTION: {exc}")
            break

    total_ms = int((time.perf_counter() - pipeline_start) * 1000)
    return {"stage_results": stage_results, "total_ms": total_ms}


def _build_settings(profile: str, skip_rate: int, adaptive: bool, roi_zones: list) -> dict:
    PROFILES = {
        "fast":     {"detection_model": "yolo11n.pt", "pose_model": None},
        "balanced": {"detection_model": "yolo11l.pt", "pose_model": "yolov8n-pose.pt"},
        "accuracy": {"detection_model": "yolo11x.pt", "pose_model": "yolo11x-pose.pt"},
    }
    prof = PROFILES.get(profile, PROFILES["accuracy"])
    return {
        "detection_model":       prof["detection_model"],
        "pose_model":            prof["pose_model"],
        "frame_skip_rate":       skip_rate,
        "adaptive_skip":         adaptive,
        "roi_zones":             roi_zones,
        "confidence_threshold":  0.25,
        "sahi_enabled":          False,
        "low_light_enabled":     True,
        "benchmark_mode":        True,  # suppress heavy summarization
    }


def _extract_summary_metrics(stage_results: list) -> dict:
    """Pull key metrics out of stage results for top-level summary."""
    def stage(name):
        return next((s for s in stage_results if s["name"] == name), {})

    s02 = stage("s02_extract").get("metrics", {})
    s04 = stage("s04_object_detect").get("metrics", {})
    s07 = stage("s07_event_understand").get("metrics", {})
    s12 = stage("s12_export").get("metrics", {})

    return {
        "frames_extracted":        s02.get("frames_extracted"),
        "processing_profile":      s02.get("processing_profile"),
        "adaptive_skip_enabled":   s02.get("adaptive_skip_enabled", False),
        "effective_sampling_ratio": s02.get("effective_sampling_ratio"),
        "total_detections":        s04.get("total_detections"),
        "low_light_frames":        s04.get("low_light_frames"),
        "unusable_frames":         s04.get("unusable_frames_skipped"),
        "total_events":            s07.get("total_events"),
        "event_types":             s07.get("event_types", {}),
        "temporal_pose_events":    s07.get("temporal_pose_events"),
        "roi_events":              s07.get("roi_events"),
        "thumbnails_generated":    s12.get("thumbnails_generated"),
        "clips_generated":         s12.get("clips_generated"),
    }


def run_benchmark(
    video_meta: dict,
    profile: str,
    skip_rate: int,
    adaptive: bool,
    roi_zones: list | None = None,
    benchmark_num: int | None = None,
    label: str | None = None,
) -> dict:
    """Run one benchmark and write result JSON. Returns result dict."""
    video_path = video_meta["path"]
    video_id   = video_meta["video_id"]
    duration_s = video_meta.get("duration_s", 0)

    if not Path(video_path).exists():
        print(f"  ✗ Video not found: {video_path}")
        return {"error": "video_not_found", "path": video_path}

    num = benchmark_num or _next_benchmark_num()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS_DIR / f"benchmark-{num:03d}.json"

    job_id = f"bench-{num:03d}-{int(time.time())}"
    settings = _build_settings(profile, skip_rate, adaptive, roi_zones or [])

    print(f"\n{'='*60}")
    print(f"Benchmark {num:03d}: {video_id}")
    print(f"  Video:   {video_path}")
    print(f"  Profile: {profile}  skip={skip_rate}  adaptive={adaptive}")
    print(f"  Label:   {label or 'unlabelled'}")
    print(f"{'='*60}")

    t0 = time.perf_counter()
    try:
        pipeline_out = asyncio.run(_run_pipeline(video_path, settings, job_id))
    except Exception as exc:
        pipeline_out = {
            "stage_results": [],
            "total_ms": int((time.perf_counter() - t0) * 1000),
            "fatal_error": str(exc),
        }
        print(f"  ✗ Pipeline fatal error: {exc}")

    wall_ms = int((time.perf_counter() - t0) * 1000)
    wall_s  = wall_ms / 1000.0
    rtf     = wall_s / duration_s if duration_s > 0 else None

    summary = _extract_summary_metrics(pipeline_out.get("stage_results", []))

    result = {
        "config": {
            "version":    "v1.0.1-accuracy-overhaul",
            "git_commit": _git_commit(),
            "profile":    profile,
            "skip_rate":  skip_rate,
            "adaptive_skip": adaptive,
            "benchmark_label": label,
        },
        "hardware": {
            "gpu":      _gpu_info(),
            "ram_mb":   _ram_mb(),
            "platform": platform.platform(),
        },
        "video": {
            "video_id":    video_id,
            "path":        video_path,
            "duration_s":  duration_s,
            "resolution":  video_meta.get("resolution"),
            "fps":         video_meta.get("fps"),
            "description": video_meta.get("description"),
            "limitation":  video_meta.get("limitation"),
        },
        "timing": {
            "wall_time_s":   wall_s,
            "pipeline_ms":   pipeline_out.get("total_ms"),
            "real_time_factor": rtf,
        },
        "metrics": summary,
        "stage_results": pipeline_out.get("stage_results", []),
        "fatal_error": pipeline_out.get("fatal_error"),
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "note": (
            "ground_truth_available=false. "
            "precision/recall/F1 are null. "
            "Detection counts on synthetic videos are expected to be low or zero "
            "because YOLO models are not trained to detect geometric shapes."
        ),
        "ground_truth_available": False,
        "detection_precision": None,
        "detection_recall":    None,
        "detection_f1":        None,
    }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"\n  Wall time: {wall_s:.1f}s  RTF: {rtf:.2f}x" if rtf else f"\n  Wall time: {wall_s:.1f}s")
    print(f"  Events generated: {summary.get('total_events')}")
    print(f"  Detections: {summary.get('total_detections')}")
    print(f"  Result: {result_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="TCE Phase 4 Benchmark Runner")
    parser.add_argument("--all", action="store_true", help="Run all videos in manifest")
    parser.add_argument("--video", help="Run specific video_id")
    parser.add_argument("--profile", default="accuracy", choices=["fast", "balanced", "accuracy"])
    parser.add_argument("--skip", type=int, default=5)
    parser.add_argument("--adaptive", action="store_true")
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        print("Run: python backend/scripts/generate_validation_corpus.py first")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        manifest = json.load(f)
    videos = manifest["videos"]

    if args.video:
        videos = [v for v in videos if v["video_id"] == args.video]
        if not videos:
            print(f"Video ID '{args.video}' not found in manifest")
            sys.exit(1)
    elif not args.all:
        print("Specify --all or --video VIDEO_ID")
        sys.exit(1)

    print(f"TCE Phase 4 Benchmark Runner")
    print(f"  Commit: {_git_commit()}")
    print(f"  GPU:    {_gpu_info()}")
    print(f"  Videos: {len(videos)}")
    print(f"  Profile: {args.profile}  skip={args.skip}  adaptive={args.adaptive}")

    results = []
    for i, video in enumerate(videos, start=1):
        num = _next_benchmark_num()
        r = run_benchmark(
            video_meta=video,
            profile=args.profile,
            skip_rate=args.skip,
            adaptive=args.adaptive,
            benchmark_num=num,
            label=f"phase4-{args.profile}",
        )
        results.append(r)

    # Write aggregate summary
    summary_path = RESULTS_DIR / "summary.json"
    agg = {
        "ran_at":    time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git_commit": _git_commit(),
        "profile":   args.profile,
        "videos_run": len(results),
        "results":   [
            {
                "video_id":   r.get("video", {}).get("video_id"),
                "rtf":        r.get("timing", {}).get("real_time_factor"),
                "events":     r.get("metrics", {}).get("total_events"),
                "detections": r.get("metrics", {}).get("total_detections"),
                "error":      r.get("fatal_error"),
            }
            for r in results if isinstance(r, dict) and "video" in r
        ],
    }
    with open(summary_path, "w") as f:
        json.dump(agg, f, indent=2, default=str)
    print(f"\n{'='*60}")
    print(f"Benchmark run complete. {len(results)} videos processed.")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
