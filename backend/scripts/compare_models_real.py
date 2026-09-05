"""
Phase 5F — Model Comparison on Real Footage.
Runs archive_001 (60s clip) through yolo11n, yolo11l, yolo11x.
Winner selected from measured evidence only.
"""
import json, sys, time, tempfile
from pathlib import Path
import cv2, torch

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
VIDEO = REPO_ROOT / "data/real/archive/videos/WhenYouA1948_512kb.mp4"
CLIP_S = 60


def extract_clip(src, dur_s, dst):
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(3)), int(cap.get(4))
    frames_to_write = min(int(fps * dur_s), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    out = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = 0
    while n < frames_to_write:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame); n += 1
    cap.release(); out.release()
    return n, fps, w, h


def run_model(clip_path, model_name, skip=5):
    from ultralytics import YOLO
    model = YOLO(model_name)
    cap = cv2.VideoCapture(clip_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    vram0 = torch.cuda.memory_allocated(0)//1024**2 if torch.cuda.is_available() else 0
    t0 = time.perf_counter()
    processed = 0; total_det = 0; frames_with = 0; max_sim = 0
    fi = 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        if fi % skip == 0:
            r = model(frame, verbose=False, classes=[0])
            n = len(r[0].boxes) if r[0].boxes else 0
            total_det += n; frames_with += (1 if n > 0 else 0)
            max_sim = max(max_sim, n); processed += 1
        fi += 1
    cap.release()
    elapsed = time.perf_counter() - t0
    vram1 = torch.cuda.memory_allocated(0)//1024**2 if torch.cuda.is_available() else 0
    return {
        "model": model_name,
        "frames_processed": processed,
        "total_detections": total_det,
        "frames_with_persons": frames_with,
        "frames_with_persons_pct": round(frames_with/max(processed,1)*100,1),
        "max_simultaneous": max_sim,
        "detection_fps": round(processed/elapsed,1),
        "processing_time_s": round(elapsed,2),
        "rtf": round(elapsed/(total/fps),3),
        "vram_delta_mb": vram1 - vram0,
    }


def main():
    if not VIDEO.exists():
        print(f"ERROR: {VIDEO} not found"); sys.exit(1)
    print(f"Phase 5F — Model Comparison on Real Footage")
    print(f"Clip: {VIDEO.name}, first {CLIP_S}s\n")

    with tempfile.TemporaryDirectory() as tmp:
        clip = str(Path(tmp) / "clip.mp4")
        nf, fps, w, h = extract_clip(str(VIDEO), CLIP_S, clip)
        print(f"Clip: {w}x{h} @ {fps:.1f}fps, {nf} frames\n")

        results = []
        for model_name in ["yolo11n.pt", "yolo11l.pt", "yolo11x.pt"]:
            print(f"Running {model_name}...")
            r = run_model(clip, model_name, skip=5)
            results.append(r)
            print(f"  Detections: {r['total_detections']:5d}  "
                  f"frames_with={r['frames_with_persons_pct']:5.1f}%  "
                  f"max_sim={r['max_simultaneous']}  "
                  f"FPS={r['detection_fps']:5.1f}  "
                  f"RTF={r['rtf']:.3f}x  "
                  f"VRAM_delta={r['vram_delta_mb']}MB")

    print()
    print("="*72)
    print(f"{'Model':<12} {'Detections':>11} {'Frames%':>9} {'MaxSim':>8} {'FPS':>7} {'RTF':>7} {'VRAM+MB':>8}")
    print("="*72)
    for r in results:
        print(f"{r['model']:<12} {r['total_detections']:>11} "
              f"{r['frames_with_persons_pct']:>8.1f}% "
              f"{r['max_simultaneous']:>8} "
              f"{r['detection_fps']:>7.1f} "
              f"{r['rtf']:>7.3f}x "
              f"{r['vram_delta_mb']:>8}")
    print("="*72)

    # Select winner
    best = max(results, key=lambda r: r["total_detections"])
    efficient = min(results, key=lambda r: r["vram_delta_mb"])
    print(f"\nMost detections:  {best['model']}")
    print(f"Most VRAM-efficient: {efficient['model']}")

    # Save
    out = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "clip": {"file": VIDEO.name, "duration_s": CLIP_S, "frames": nf, "fps": fps},
        "models": results,
        "note": "Winner selected by evidence only. More detections not automatically better — may include false positives.",
    }
    out_json = RESULTS_DIR / "model-comparison-real.json"
    with open(out_json, "w") as f: json.dump(out, f, indent=2)

    # Markdown report
    md = REPORTS_DIR / "model-comparison-real.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Model Comparison on Real Footage — Phase 5F\n\n")
        f.write(f"Clip: `{VIDEO.name}` first {CLIP_S}s | {w}x{h} @ {fps:.1f}fps  \n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n\n")
        f.write("| Model | Total Det | Frames% | MaxSim | Det FPS | RTF | VRAM +MB |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['model']} | {r['total_detections']} | {r['frames_with_persons_pct']}% "
                    f"| {r['max_simultaneous']} | {r['detection_fps']} | {r['rtf']}x | {r['vram_delta_mb']} |\n")
        f.write("\n## Findings\n\n")
        f.write(f"- Most detections: **{best['model']}**\n")
        f.write(f"- Most VRAM-efficient: **{efficient['model']}**\n")
        f.write("- Note: higher detection count is NOT necessarily better — may include false positives.\n")
        f.write("- Ground truth unavailable — cannot compute precision/recall/F1.\n")
        f.write("\n## Capability Classification\n\n")
        f.write("| Capability | Status |\n|---|---|\n")
        f.write("| Multi-model comparison infrastructure | **PROVEN** |\n")
        f.write("| Detection count on real footage | **PARTIALLY VALIDATED** |\n")
        f.write("| Precision/recall by model | **NOT YET VALIDATED** (no ground truth) |\n")

    print(f"\nResults: {out_json}")
    print(f"Report:  {md}")


if __name__ == "__main__":
    main()
