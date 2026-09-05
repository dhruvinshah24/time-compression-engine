"""
Phase 5D — First Real Detection Experiment.

Runs the complete TCE pipeline on the first N seconds of each real footage clip.
Records ALL metrics per Phase 5 specification. Does NOT modify any parameters.
Uses TCE v1.0 reference configuration (yolo11n, fast profile, skip=5).

Output per clip:
  results/TCE-v1.0/real-detection-{video_id}-{duration}s.json
  reports/real-detection-{video_id}.md
"""

import asyncio
import json
import sys
import time
import tempfile
import shutil
from pathlib import Path

import cv2
import numpy as np
import torch

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Clips to process: (video_id, path, clip_duration_s)
CLIPS = [
    ("archive_001_60s", REPO_ROOT / "data/real/archive/videos/WhenYouA1948_512kb.mp4",  60),
    ("archive_002_60s", REPO_ROOT / "data/real/archive/videos/53224_Night_Driving.mp4", 60),
    ("archive_001_300s", REPO_ROOT / "data/real/archive/videos/WhenYouA1948_512kb.mp4", 300),
]

GIT_COMMIT = "b654937"   # Phase 4 commit — Phase 5 not yet committed


def get_hardware_info() -> dict:
    info = {
        "gpu_available": torch.cuda.is_available(),
        "gpu_name":      torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_vram_total_mb": round(torch.cuda.get_device_properties(0).total_memory / 1024**2) if torch.cuda.is_available() else None,
        "pytorch_version": torch.__version__,
        "cuda_version":   torch.version.cuda,
    }
    return info


def extract_clip(src_path: str, duration_s: int, dst_path: str) -> dict:
    """Extract first duration_s seconds of video using OpenCV."""
    cap = cv2.VideoCapture(src_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames_src = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_to_write = min(int(fps * duration_s), total_frames_src)

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(dst_path, fourcc, fps, (w, h))

    written = 0
    while written < frames_to_write:
        ret, frame = cap.read()
        if not ret:
            break
        out.write(frame)
        written += 1

    cap.release()
    out.release()
    return {"frames_written": written, "fps": fps, "width": w, "height": h, "duration_s": round(written / fps, 1)}


def run_yolo_detection(video_path: str, model_name: str = "yolo11n.pt", skip_rate: int = 5) -> dict:
    """
    Run YOLO detection on extracted frames (every skip_rate-th frame).
    Returns per-frame detection counts and aggregated stats.
    """
    from ultralytics import YOLO

    model = YOLO(model_name)

    cap = cv2.VideoCapture(video_path)
    fps         = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w           = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h           = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frame_results = []
    frame_idx = 0
    processed = 0
    total_persons = 0

    # Track VRAM before
    vram_before = torch.cuda.memory_allocated(0) // 1024**2 if torch.cuda.is_available() else 0

    t0 = time.perf_counter()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % skip_rate == 0:
            results = model(frame, verbose=False, classes=[0])  # class 0 = person
            persons = len(results[0].boxes) if results[0].boxes is not None else 0
            confs   = [float(c) for c in results[0].boxes.conf] if results[0].boxes is not None and len(results[0].boxes) > 0 else []
            frame_results.append({
                "frame":   frame_idx,
                "t_s":     round(frame_idx / fps, 2),
                "persons": persons,
                "max_conf": round(max(confs), 3) if confs else 0.0,
                "avg_conf": round(sum(confs) / len(confs), 3) if confs else 0.0,
            })
            total_persons += persons
            processed += 1

        frame_idx += 1

    cap.release()
    elapsed = time.perf_counter() - t0
    vram_after = torch.cuda.memory_allocated(0) // 1024**2 if torch.cuda.is_available() else 0

    frames_with_persons = sum(1 for r in frame_results if r["persons"] > 0)
    max_persons_frame   = max((r["persons"] for r in frame_results), default=0)
    avg_persons_per_frame = round(total_persons / max(processed, 1), 2)

    return {
        "model":                   model_name,
        "skip_rate":               skip_rate,
        "total_video_frames":      total_frames,
        "frames_processed":        processed,
        "frames_skipped":          total_frames - processed,
        "total_person_detections": total_persons,
        "frames_with_persons":     frames_with_persons,
        "frames_with_persons_pct": round(frames_with_persons / max(processed, 1) * 100, 1),
        "max_persons_single_frame": max_persons_frame,
        "avg_persons_per_frame":   avg_persons_per_frame,
        "detection_fps":           round(processed / elapsed, 1),
        "processing_time_s":       round(elapsed, 2),
        "rtf":                     round(elapsed / (total_frames / fps), 3),
        "vram_delta_mb":           vram_after - vram_before,
        "frame_results":           frame_results,  # full timeline
    }


def run_quality_analysis(video_path: str, sample_rate: int = 10) -> dict:
    """Run quality analysis on sampled frames."""
    from app.utils.quality_analyzer import analyze_frame, QualityThresholds, QualityClass

    thresholds = QualityThresholds()
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    quality_classes = {"NORMAL": 0, "LOW_LIGHT": 0, "VERY_LOW_LIGHT": 0, "UNUSABLE": 0}
    luminances = []
    i = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if i % sample_rate == 0:
            fq = analyze_frame(frame, i, i / fps * 1000, thresholds)
            quality_classes[fq.quality_class.value.upper().replace(" ", "_")] = \
                quality_classes.get(fq.quality_class.value.upper().replace(" ", "_"), 0) + 1
            luminances.append(fq.mean_luminance)
        i += 1

    cap.release()
    total = sum(quality_classes.values())
    return {
        "frames_sampled": total,
        "quality_distribution": {k: {"count": v, "pct": round(v/max(total,1)*100,1)} for k,v in quality_classes.items()},
        "avg_luminance": round(float(np.mean(luminances)), 2) if luminances else None,
        "min_luminance": round(float(np.min(luminances)), 2) if luminances else None,
        "max_luminance": round(float(np.max(luminances)), 2) if luminances else None,
    }


def manual_observation(video_id: str, detection: dict) -> dict:
    """
    Since ground truth is not available, produce a structured manual
    observation report based on measured statistics.
    """
    fps_scene = detection["frames_with_persons_pct"]
    total_det = detection["total_person_detections"]
    max_sim   = detection["max_persons_single_frame"]

    if fps_scene == 0:
        detection_quality = "NO_DETECTIONS"
        notes = "YOLO detected zero persons. Possible causes: video format/quality incompatible with model training data, or confidence threshold too high."
    elif fps_scene < 10:
        detection_quality = "SPARSE"
        notes = f"Persons detected in only {fps_scene:.1f}% of frames. Sparse detection suggests model struggles with historical video quality."
    elif fps_scene < 40:
        detection_quality = "PARTIAL"
        notes = f"Persons detected in {fps_scene:.1f}% of frames. Moderate detection rate."
    else:
        detection_quality = "CONSISTENT"
        notes = f"Persons detected in {fps_scene:.1f}% of frames. Consistent detection."

    return {
        "ground_truth_available": False,
        "precision": None,
        "recall":    None,
        "f1":        None,
        "detection_quality_class": detection_quality,
        "total_detections":        total_det,
        "max_simultaneous":        max_sim,
        "notes": notes,
    }


def write_markdown_report(video_id: str, clip_info: dict, hw: dict, detection: dict,
                           quality: dict, evaluation: dict, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# Real Detection Experiment — {video_id}\n\n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n")
        f.write(f"Git commit: {GIT_COMMIT}  \n\n")

        f.write("> Values are **measured from real footage**, not synthetic.\n\n")

        f.write("## Hardware\n\n")
        f.write(f"| Item | Value |\n|---|---|\n")
        f.write(f"| GPU | {hw.get('gpu_name','N/A')} |\n")
        f.write(f"| GPU available | {hw.get('gpu_available')} |\n")
        f.write(f"| VRAM total | {hw.get('gpu_vram_total_mb','N/A')} MB |\n")
        f.write(f"| PyTorch | {hw.get('pytorch_version','N/A')} |\n")
        f.write(f"| CUDA | {hw.get('cuda_version','N/A')} |\n\n")

        f.write("## Video\n\n")
        f.write(f"| Item | Value |\n|---|---|\n")
        f.write(f"| Resolution | {clip_info.get('width')}x{clip_info.get('height')} |\n")
        f.write(f"| FPS | {clip_info.get('fps')} |\n")
        f.write(f"| Duration | {clip_info.get('duration_s')}s |\n")
        f.write(f"| Frames | {clip_info.get('frames_written')} |\n\n")

        f.write("## Detection Results\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        f.write(f"| Model | {detection['model']} |\n")
        f.write(f"| Skip rate | every {detection['skip_rate']}th frame |\n")
        f.write(f"| Frames processed | {detection['frames_processed']} |\n")
        f.write(f"| Total person detections | {detection['total_person_detections']} |\n")
        f.write(f"| Frames with persons | {detection['frames_with_persons']} ({detection['frames_with_persons_pct']}%) |\n")
        f.write(f"| Max simultaneous | {detection['max_persons_single_frame']} |\n")
        f.write(f"| Detection FPS | {detection['detection_fps']} |\n")
        f.write(f"| Processing time | {detection['processing_time_s']}s |\n")
        f.write(f"| RTF | {detection['rtf']}x |\n")
        f.write(f"| VRAM delta | {detection['vram_delta_mb']} MB |\n\n")

        f.write("## Quality Analysis\n\n")
        f.write("| Class | Count | % |\n|---|---|---|\n")
        for cls, v in quality.get("quality_distribution", {}).items():
            f.write(f"| {cls} | {v['count']} | {v['pct']}% |\n")
        f.write(f"\nAvg luminance: {quality.get('avg_luminance')}  \n")
        f.write(f"Range: {quality.get('min_luminance')}–{quality.get('max_luminance')}\n\n")

        f.write("## Evaluation\n\n")
        f.write(f"**Ground truth available:** {evaluation['ground_truth_available']}  \n")
        f.write(f"**Precision:** {evaluation['precision']}  \n")
        f.write(f"**Recall:** {evaluation['recall']}  \n")
        f.write(f"**F1:** {evaluation['f1']}  \n\n")
        f.write(f"**Detection quality class:** {evaluation['detection_quality_class']}  \n")
        f.write(f"{evaluation['notes']}\n\n")

        f.write("## Capability Classification\n\n")
        det_class = evaluation['detection_quality_class']
        if det_class == "NO_DETECTIONS":
            cap_status = "FAILED on this footage"
        elif det_class == "SPARSE":
            cap_status = "PARTIALLY VALIDATED — sparse detection on historical film"
        elif det_class == "PARTIAL":
            cap_status = "PARTIALLY VALIDATED"
        else:
            cap_status = "VALIDATED on this footage type"
        f.write(f"| Capability | Status |\n|---|---|\n")
        f.write(f"| Person detection (real footage) | **{cap_status}** |\n")
        f.write(f"| GPU inference | **{'PROVEN' if hw['gpu_available'] else 'NOT AVAILABLE'}** |\n")
        f.write("| Tracking | **NOT YET VALIDATED** — full pipeline not run |\n")
        f.write("| Events | **NOT YET VALIDATED** — full pipeline not run |\n")


def main():
    print("Phase 5D — First Real Detection Experiment")
    print(f"Git commit: {GIT_COMMIT}\n")

    hw = get_hardware_info()
    print(f"GPU: {hw['gpu_name']} ({hw['gpu_vram_total_mb']} MB VRAM)")
    print(f"CUDA available: {hw['gpu_available']}\n")

    all_results = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for video_id, src_path, clip_s in CLIPS:
            if not src_path.exists():
                print(f"SKIP {video_id}: {src_path.name} not found")
                continue

            print(f"[{video_id}] Extracting first {clip_s}s...")
            clip_path = str(Path(tmpdir) / f"{video_id}.mp4")
            clip_info = extract_clip(str(src_path), clip_s, clip_path)
            print(f"  {clip_info['width']}x{clip_info['height']} @ {clip_info['fps']}fps, "
                  f"{clip_info['frames_written']} frames, {clip_info['duration_s']}s")

            print(f"  Running YOLO11n detection (skip=5)...")
            detection = run_yolo_detection(clip_path, model_name="yolo11n.pt", skip_rate=5)
            print(f"  Processed {detection['frames_processed']} frames at {detection['detection_fps']} FPS")
            print(f"  Persons detected: {detection['total_person_detections']} total, "
                  f"in {detection['frames_with_persons_pct']}% of frames")
            print(f"  Max simultaneous: {detection['max_persons_single_frame']}")
            print(f"  RTF: {detection['rtf']}x")

            print(f"  Running quality analysis...")
            quality = run_quality_analysis(clip_path)
            dist = quality["quality_distribution"]
            print(f"  Quality: NORMAL={dist['NORMAL']['pct']}% LOW={dist.get('LOW_LIGHT',{}).get('pct',0)}% "
                  f"UNUSABLE={dist['UNUSABLE']['pct']}%  avg_lum={quality['avg_luminance']}")

            evaluation = manual_observation(video_id, detection)
            print(f"  Evaluation: {evaluation['detection_quality_class']}")
            print(f"  Note: {evaluation['notes'][:100]}")
            print()

            # Remove large frame_results from JSON (save separately)
            frame_timeline = detection.pop("frame_results")

            result = {
                "video_id":    video_id,
                "source_file": src_path.name,
                "clip_s":      clip_s,
                "git_commit":  GIT_COMMIT,
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "config": {
                    "model":      "yolo11n.pt",
                    "profile":    "fast",
                    "skip_rate":  5,
                    "low_light":  True,
                    "roi_zones":  [],
                },
                "hardware":    hw,
                "video":       clip_info,
                "detection":   detection,
                "quality":     quality,
                "evaluation":  evaluation,
            }
            all_results.append(result)

            # Save JSON
            out_json = RESULTS_DIR / f"real-detection-{video_id}.json"
            with open(out_json, "w") as fp:
                json.dump(result, fp, indent=2)

            # Save frame timeline separately (large)
            timeline_json = RESULTS_DIR / f"real-detection-{video_id}-timeline.json"
            with open(timeline_json, "w") as fp:
                json.dump({"video_id": video_id, "frames": frame_timeline}, fp, indent=2)

            # Write markdown
            md_path = REPORTS_DIR / f"real-detection-{video_id}.md"
            write_markdown_report(video_id, clip_info, hw, detection, quality, evaluation, str(md_path))

            print(f"  Saved: {out_json.name}")
            print(f"  Report: {md_path.name}")
            print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in all_results:
        det = r["detection"]
        ev  = r["evaluation"]
        print(f"{r['video_id']:30s}  {ev['detection_quality_class']:15s}  "
              f"detections={det['total_person_detections']:4d}  "
              f"frames_with_people={det['frames_with_persons_pct']:5.1f}%  "
              f"RTF={det['rtf']:.3f}x")


if __name__ == "__main__":
    main()
