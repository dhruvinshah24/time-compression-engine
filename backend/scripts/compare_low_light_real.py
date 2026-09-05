"""
Phase 5E — Low-Light Comparison on Real Footage.

Uses archive_002 (LAPD night driving film, 1950s, 640x360 @ 24fps).
This clip was classified: 45.8% NORMAL, 38.2% LOW_LIGHT, 10.4% UNUSABLE.

Compares:
  - YOLO11n WITHOUT preprocessing
  - YOLO11n WITH low-light preprocessing (CLAHE + gamma)

Records:
  - Person detections
  - Frames with detections
  - Quality classifications
  - Processing overhead

Does NOT fabricate improvement if none exists.
"""
import json, sys, time, tempfile
from pathlib import Path
import cv2, numpy as np, torch

BACKEND_DIR = Path(__file__).parent.parent
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

RESULTS_DIR = REPO_ROOT / "results" / "TCE-v1.0"
REPORTS_DIR = REPO_ROOT / "reports"
VIDEO = REPO_ROOT / "data/real/archive/videos/53224_Night_Driving.mp4"
CLIP_S = 120  # 2 minutes of night footage


def extract_clip(src, dur_s, dst):
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(3)), int(cap.get(4))
    nf = min(int(fps*dur_s), int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    out = cv2.VideoWriter(dst, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    n = 0
    while n < nf:
        ret, frame = cap.read()
        if not ret: break
        out.write(frame); n += 1
    cap.release(); out.release()
    return n, fps, w, h


def apply_preprocessing(frame):
    """CLAHE + gamma — same as low_light.py logic."""
    from app.utils.quality_analyzer import analyze_frame, QualityThresholds
    fq = analyze_frame(frame, 0, 0.0, QualityThresholds())
    from app.utils.low_light import preprocess_frame
    result = preprocess_frame(frame, fq, mode='auto')
    return result.frame


def run_detection(clip_path, use_preprocessing: bool, skip=5):
    from ultralytics import YOLO
    model = YOLO("yolo11n.pt")

    cap = cv2.VideoCapture(clip_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    t0 = time.perf_counter()
    processed = 0; total_det = 0; frames_with = 0; max_sim = 0
    preprocessing_overhead_ms = []
    fi = 0

    while True:
        ret, frame = cap.read()
        if not ret: break
        if fi % skip == 0:
            if use_preprocessing:
                tp0 = time.perf_counter()
                frame = apply_preprocessing(frame)
                preprocessing_overhead_ms.append((time.perf_counter()-tp0)*1000)
            r = model(frame, verbose=False, classes=[0])
            n = len(r[0].boxes) if r[0].boxes else 0
            total_det += n; frames_with += (1 if n > 0 else 0)
            max_sim = max(max_sim, n); processed += 1
        fi += 1

    cap.release()
    elapsed = time.perf_counter() - t0
    avg_pp = round(float(np.mean(preprocessing_overhead_ms)), 2) if preprocessing_overhead_ms else 0.0

    return {
        "use_preprocessing": use_preprocessing,
        "frames_processed": processed,
        "total_detections": total_det,
        "frames_with_persons": frames_with,
        "frames_with_persons_pct": round(frames_with/max(processed,1)*100,1),
        "max_simultaneous": max_sim,
        "processing_time_s": round(elapsed,2),
        "rtf": round(elapsed/(total/fps),3),
        "avg_preprocessing_overhead_ms": avg_pp,
    }


def main():
    if not VIDEO.exists():
        print(f"ERROR: {VIDEO} not found"); sys.exit(1)

    print("Phase 5E — Low-Light Comparison on Real Footage")
    print(f"Clip: {VIDEO.name}, first {CLIP_S}s\n")

    with tempfile.TemporaryDirectory() as tmp:
        clip = str(Path(tmp) / "night_clip.mp4")
        nf, fps, w, h = extract_clip(str(VIDEO), CLIP_S, clip)
        print(f"Clip: {w}x{h} @ {fps:.1f}fps, {nf} frames\n")

        print("Running WITHOUT preprocessing...")
        r_raw = run_detection(clip, use_preprocessing=False)
        print(f"  Detections: {r_raw['total_detections']}  "
              f"frames_with={r_raw['frames_with_persons_pct']}%  "
              f"RTF={r_raw['rtf']}x")

        print("Running WITH preprocessing (CLAHE+gamma)...")
        r_pp = run_detection(clip, use_preprocessing=True)
        print(f"  Detections: {r_pp['total_detections']}  "
              f"frames_with={r_pp['frames_with_persons_pct']}%  "
              f"RTF={r_pp['rtf']}x  "
              f"pp_overhead={r_pp['avg_preprocessing_overhead_ms']}ms/frame")

    print()
    det_diff = r_pp["total_detections"] - r_raw["total_detections"]
    det_diff_pct = round((det_diff / max(r_raw["total_detections"], 1)) * 100, 1)
    print(f"Detection change: {'+' if det_diff >= 0 else ''}{det_diff} ({det_diff_pct:+.1f}%)")

    if det_diff > 0:
        conclusion = "IMPROVED — preprocessing increased detections on this night footage"
    elif det_diff < 0:
        conclusion = "REDUCED — preprocessing reduced detections on this night footage"
    else:
        conclusion = "NO CHANGE — preprocessing had no measurable effect on detection count"

    print(f"Conclusion: {conclusion}")

    out = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "clip": {"file": VIDEO.name, "duration_s": CLIP_S, "frames": nf, "fps": fps, "resolution": f"{w}x{h}"},
        "without_preprocessing": r_raw,
        "with_preprocessing": r_pp,
        "detection_delta": det_diff,
        "detection_delta_pct": det_diff_pct,
        "conclusion": conclusion,
    }
    out_json = RESULTS_DIR / "low-light-comparison-real.json"
    with open(out_json, "w") as f: json.dump(out, f, indent=2)

    md = REPORTS_DIR / "low-light-comparison-real.md"
    with open(md, "w", encoding="utf-8") as f:
        f.write("# Low-Light Comparison — Phase 5E\n\n")
        f.write(f"Clip: `{VIDEO.name}` first {CLIP_S}s | {w}x{h} @ {fps:.1f}fps  \n")
        f.write(f"Measured: {time.strftime('%Y-%m-%d %H:%M')}  \n\n")
        f.write("| Metric | Without Preprocessing | With Preprocessing | Delta |\n|---|---|---|---|\n")
        f.write(f"| Total detections | {r_raw['total_detections']} | {r_pp['total_detections']} | {det_diff:+d} |\n")
        f.write(f"| Frames with persons | {r_raw['frames_with_persons_pct']}% | {r_pp['frames_with_persons_pct']}% | — |\n")
        f.write(f"| Max simultaneous | {r_raw['max_simultaneous']} | {r_pp['max_simultaneous']} | — |\n")
        f.write(f"| Processing time | {r_raw['processing_time_s']}s | {r_pp['processing_time_s']}s | — |\n")
        f.write(f"| RTF | {r_raw['rtf']}x | {r_pp['rtf']}x | — |\n")
        f.write(f"| Preprocessing overhead | N/A | {r_pp['avg_preprocessing_overhead_ms']}ms/frame | — |\n")
        f.write(f"\n## Conclusion\n\n**{conclusion}**  \n")
        f.write(f"Detection change: {det_diff_pct:+.1f}%\n\n")
        f.write("## Capability Classification\n\n")
        f.write("| Capability | Status |\n|---|---|\n")
        if det_diff > 0:
            f.write("| Low-light preprocessing improves detection | **PARTIALLY VALIDATED** on 1950s night film |\n")
        elif det_diff < 0:
            f.write("| Low-light preprocessing improves detection | **FAILED** on this footage — reduced detections |\n")
        else:
            f.write("| Low-light preprocessing improves detection | **NOT VALIDATED** — no measurable effect |\n")
        f.write("| Modern night CCTV preprocessing | **NOT YET VALIDATED** — no modern night footage |\n")

    print(f"\nResults: {out_json}")
    print(f"Report:  {md}")


if __name__ == "__main__":
    main()
