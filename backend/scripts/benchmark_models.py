"""
Model Comparison Benchmark — YOLO11n / YOLO11l / YOLO11x / YOLO11x-pose.

Measures FPS, VRAM usage, and detection behaviour on a standard test video.
Writes results to reports/model-comparison.md.

Usage:
    python backend/scripts/benchmark_models.py

This script measures:
1. Model load time
2. Inference FPS on a fixed input size (1080p)
3. VRAM used immediately after loading
4. VRAM used during inference
5. Number of detections on the corpus EXP-A video

It does NOT measure:
- Precision or Recall (no ground truth available)
- mAP (would require labelled dataset)
- Detection quality (qualitative only — logged to stdout)

All results are measured values, not theoretical claims.
"""

import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = REPO_ROOT / "reports"
RESULTS_DIR.mkdir(exist_ok=True)

TEST_VIDEO = REPO_ROOT / "data" / "real" / "synthetic" / "normal_light_walking_60s.mp4"
BENCHMARK_FRAMES = 100   # frames to run inference on for FPS measurement
WARMUP_FRAMES = 10


def _vram_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_allocated(0) // (1024 * 1024)
    except Exception:
        pass
    return None


def _vram_reserved_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.memory_reserved(0) // (1024 * 1024)
    except Exception:
        pass
    return None


def benchmark_model(model_name: str, conf: float = 0.25) -> dict:
    """Benchmark one YOLO model. Returns dict of measured metrics."""
    print(f"\n{'='*50}")
    print(f"Benchmarking: {model_name}")
    print(f"{'='*50}")

    result = {
        "model": model_name,
        "conf": conf,
        "status": "not_run",
        "error": None,
    }

    try:
        import torch
        import cv2
        from ultralytics import YOLO

        gpu_available = torch.cuda.is_available()
        device = "cuda" if gpu_available else "cpu"
        print(f"  Device: {device}")

        # ── Load model ────────────────────────────────────────────────────
        if gpu_available:
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
            vram_before = _vram_reserved_mb()

        t_load = time.perf_counter()
        model = YOLO(model_name)
        model.to(device)
        load_time_s = time.perf_counter() - t_load

        if gpu_available:
            torch.cuda.synchronize()
        vram_after_load = _vram_reserved_mb()
        vram_load_mb = (vram_after_load - (vram_before or 0)) if vram_after_load else None
        print(f"  Loaded in {load_time_s:.2f}s  VRAM after load: {vram_after_load}MB")

        result["load_time_s"]     = round(load_time_s, 3)
        result["vram_after_load_mb"] = vram_after_load

        # ── Create test frames from synthetic video ────────────────────────
        if not TEST_VIDEO.exists():
            # Fall back to blank 1080p frames
            import numpy as np
            frames = [
                np.full((1080, 1920, 3), 80, dtype=np.uint8)
                for _ in range(BENCHMARK_FRAMES + WARMUP_FRAMES)
            ]
            frame_source = "blank_1080p"
        else:
            cap = cv2.VideoCapture(str(TEST_VIDEO))
            frames = []
            while len(frames) < BENCHMARK_FRAMES + WARMUP_FRAMES:
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        break
                frames.append(frame)
            cap.release()
            frame_source = str(TEST_VIDEO.name)

        print(f"  Frame source: {frame_source}  ({len(frames)} frames)")
        result["frame_source"] = frame_source

        # ── Warmup ────────────────────────────────────────────────────────
        print(f"  Warmup ({WARMUP_FRAMES} frames)...")
        for frame in frames[:WARMUP_FRAMES]:
            _ = model(frame, conf=conf, verbose=False, device=device)

        if gpu_available:
            torch.cuda.synchronize()
        vram_inference = _vram_reserved_mb()
        print(f"  VRAM during inference: {vram_inference}MB")
        result["vram_inference_mb"] = vram_inference

        # ── FPS measurement ────────────────────────────────────────────────
        print(f"  Measuring FPS ({BENCHMARK_FRAMES} frames)...")
        inference_frames = frames[WARMUP_FRAMES: WARMUP_FRAMES + BENCHMARK_FRAMES]
        total_detections = 0
        classes_seen: dict[str, int] = {}

        if gpu_available:
            torch.cuda.synchronize()
        t_start = time.perf_counter()

        for frame in inference_frames:
            preds = model(frame, conf=conf, verbose=False, device=device)
            for r in preds:
                if r.boxes is not None:
                    total_detections += len(r.boxes)
                    for cls_id in r.boxes.cls.tolist():
                        name = model.names.get(int(cls_id), str(int(cls_id)))
                        classes_seen[name] = classes_seen.get(name, 0) + 1

        if gpu_available:
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - t_start
        fps = BENCHMARK_FRAMES / elapsed if elapsed > 0 else 0
        ms_per_frame = (elapsed * 1000) / BENCHMARK_FRAMES if BENCHMARK_FRAMES > 0 else 0

        print(f"  FPS: {fps:.1f}  ms/frame: {ms_per_frame:.1f}")
        print(f"  Detections: {total_detections} across {BENCHMARK_FRAMES} frames")
        print(f"  Classes: {classes_seen}")

        result.update({
            "status":              "completed",
            "fps":                 round(fps, 2),
            "ms_per_frame":        round(ms_per_frame, 2),
            "frames_benchmarked":  BENCHMARK_FRAMES,
            "total_detections":    total_detections,
            "avg_detections_per_frame": round(total_detections / BENCHMARK_FRAMES, 3),
            "classes_detected":    classes_seen,
            "note": (
                f"Measured on {frame_source}. "
                "Synthetic video: expect 0 person detections (YOLO not trained on shapes). "
                "FPS is reliable. Detection counts are only meaningful on real footage."
            ),
        })

        # Cleanup
        del model
        if gpu_available:
            torch.cuda.empty_cache()

    except Exception as exc:
        import traceback
        result["status"] = "error"
        result["error"]  = str(exc)
        result["traceback"] = traceback.format_exc()[:800]
        print(f"  ERROR: {exc}")

    return result


def main():
    import torch

    print("TCE Model Comparison Benchmark")
    print(f"  Test video: {TEST_VIDEO}")
    print(f"  GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")
    print(f"  Benchmark frames: {BENCHMARK_FRAMES}")

    models_to_test = [
        "yolo11n.pt",
        "yolo11s.pt",
        "yolo11m.pt",
        "yolo11l.pt",
        "yolo11x.pt",
    ]

    results = []
    for m in models_to_test:
        r = benchmark_model(m)
        results.append(r)

    # Save raw results
    raw_path = RESULTS_DIR / "model-comparison-raw.json"
    data = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "benchmark_frames": BENCHMARK_FRAMES,
        "results": results,
    }
    with open(raw_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"\nRaw results: {raw_path}")

    # Write markdown report
    md_path = RESULTS_DIR / "model-comparison.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Model Comparison — TCE v1.0.1\n\n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n")
        f.write(f"Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}  \n")
        f.write(f"Benchmark: {BENCHMARK_FRAMES} frames @ 1080p  \n\n")
        f.write("> **Note:** FPS values are measured. Detection counts are on synthetic video.\n")
        f.write("> Detection precision/recall require real annotated footage (NOT YET AVAILABLE).\n\n")

        f.write("## Measured FPS\n\n")
        f.write("| Model | FPS (measured) | ms/frame | VRAM load (MB) | VRAM inference (MB) | Status |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in results:
            if r["status"] == "completed":
                f.write(
                    f"| {r['model']} "
                    f"| {r.get('fps', 'N/A')} "
                    f"| {r.get('ms_per_frame', 'N/A')} "
                    f"| {r.get('vram_after_load_mb', 'N/A')} "
                    f"| {r.get('vram_inference_mb', 'N/A')} "
                    f"| MEASURED |\n"
                )
            else:
                f.write(f"| {r['model']} | - | - | - | - | ERROR: {r.get('error', 'unknown')} |\n")

        f.write("\n## Detection Counts (Synthetic Video)\n\n")
        f.write("| Model | Total Detections | Avg/Frame | Classes Detected |\n")
        f.write("|---|---|---|---|\n")
        for r in results:
            if r["status"] == "completed":
                classes = r.get("classes_detected", {})
                class_str = ", ".join(f"{k}:{v}" for k, v in classes.items()) or "none"
                f.write(
                    f"| {r['model']} "
                    f"| {r.get('total_detections', 0)} "
                    f"| {r.get('avg_detections_per_frame', 0)} "
                    f"| {class_str} |\n"
                )

        f.write("\n## Notes\n\n")
        f.write("- Detection counts on synthetic videos are **expected to be near zero**.\n")
        f.write("  YOLO11 models are trained on COCO, not on geometric shapes.\n")
        f.write("- FPS measurements are **reliable** and hardware-dependent.\n")
        f.write("- VRAM values reflect PyTorch reserved memory, not CUDA total.\n")
        f.write("- Precision / Recall / mAP: **NOT MEASURED** — requires annotated real footage.\n\n")
        f.write("## Capability Classification\n\n")
        f.write("| Capability | Classification |\n")
        f.write("|---|---|\n")
        f.write("| FPS per model | **PROVEN** (measured this run) |\n")
        f.write("| VRAM per model | **PROVEN** (measured this run) |\n")
        f.write("| Detection accuracy on real people | **NOT YET VALIDATED** — no annotated footage |\n")
        f.write("| Best model choice | **INCONCLUSIVE** — cannot determine without real footage |\n")

    print(f"Markdown report: {md_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
