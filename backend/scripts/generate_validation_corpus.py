"""
Generate Phase 4 synthetic validation corpus.

Creates reproducible synthetic videos for every Phase 4 experiment.
Each video is designed to test a specific pipeline capability under
controlled conditions.

IMPORTANT: These are synthetic videos â€” shapes on solid/noisy backgrounds.
YOLO11x will NOT detect them as real people. Experiments using YOLO11x
on these videos test the pipeline's structural behaviour (extraction,
quality analysis, ROI logic) NOT detection accuracy.

Detection accuracy on real people can only be measured on real footage.

Videos generated:
  EXP-A: normal_light_walking_60s.mp4    â€” static bg + moving rectangle
  EXP-B: low_light_level_{a,b,c,d}.mp4  â€” 4 illumination levels
  EXP-C: fast_motion_60s.mp4            â€” static + burst + static
  EXP-D: multi_person_30s.mp4           â€” 2 moving rectangles
  EXP-E: roi_crossing_30s.mp4           â€” crossing into a zone
  EXP-G: scaling_30s.mp4 ... scaling_30min.mp4  â€” progressive scale
  EXP-H: pose_sequence_30s.mp4          â€” standingâ†’crouchingâ†’crawling bbox

Usage:
    python backend/scripts/generate_validation_corpus.py
"""

import json
import time
from pathlib import Path

import cv2
import numpy as np

BASE_DIR = Path(__file__).parent.parent.parent / "data" / "real" / "synthetic"
BASE_DIR.mkdir(parents=True, exist_ok=True)

FPS = 25
W, H = 1920, 1080

_rng = np.random.default_rng(42)  # fixed seed for reproducibility


def _make_writer(path: str) -> cv2.VideoWriter:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(p), fourcc, FPS, (W, H))
    if not out.isOpened():
        raise RuntimeError(f"VideoWriter failed: {path}")
    return out


def _noisy_bg(brightness: int = 80, noise: int = 6) -> np.ndarray:
    bg = np.full((H, W, 3), brightness, dtype=np.uint8)
    n = _rng.integers(-noise, noise + 1, (H, W, 3), dtype=np.int16)
    return np.clip(bg.astype(np.int16) + n, 0, 255).astype(np.uint8)


def _draw_rect(frame, cx, cy, rw, rh, color=(220, 220, 220)):
    x1 = max(0, cx - rw // 2)
    y1 = max(0, cy - rh // 2)
    x2 = min(W - 1, cx + rw // 2)
    y2 = min(H - 1, cy + rh // 2)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXP-A: Normal light, walking, 60 seconds
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_exp_a():
    path = str(BASE_DIR / "normal_light_walking_60s.mp4")
    out = _make_writer(path)
    total = 60 * FPS
    for i in range(total):
        t = i / FPS
        frame = _noisy_bg(80)
        # Person walks left â†’ right over 60s
        cx = int(100 + (W - 200) * (t / 60))
        cy = H // 2
        _draw_rect(frame, cx, cy, 80, 200)
        out.write(frame)
    out.release()
    print(f"  âœ“ {path}")
    return {
        "video_id": "exp_a_normal_walking",
        "path": path,
        "duration_s": 60,
        "resolution": f"{W}x{H}",
        "fps": FPS,
        "description": "Moving 80Ã—200 white rectangle on noisy gray bg. Tests frame extraction and event generation.",
        "limitation": "YOLO11x will NOT detect rectangle as person. Tests structural pipeline only.",
        "scenario": "normal_light",
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXP-B: Low-light at 4 illumination levels
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_exp_b():
    levels = [
        ("level_a_normal", 80, "NORMAL â€” brightness ~80/255"),
        ("level_b_low", 35, "LOW_LIGHT â€” brightness ~35/255"),
        ("level_c_very_low", 12, "VERY_LOW_LIGHT â€” brightness ~12/255"),
        ("level_d_unusable", 4, "UNUSABLE â€” brightness ~4/255"),
    ]
    out_dir = BASE_DIR / "low_light_4levels"
    out_dir.mkdir(exist_ok=True)
    results = []
    for name, brightness, label in levels:
        path = str(out_dir / f"{name}.mp4")
        writer = _make_writer(path)
        total = 30 * FPS
        for i in range(total):
            t = i / FPS
            frame = _noisy_bg(brightness, noise=3)
            cx = int(200 + (W - 400) * (t / 30))
            cy = H // 2
            _draw_rect(frame, cx, cy, 80, 200, color=(min(255, brightness + 60),) * 3)
            writer.write(frame)
        writer.release()
        print(f"  âœ“ {path}")
        results.append({
            "video_id": f"exp_b_{name}",
            "path": path,
            "duration_s": 30,
            "resolution": f"{W}x{H}",
            "fps": FPS,
            "brightness_level": brightness,
            "illumination_label": label,
            "description": f"Moving rectangle at {brightness}/255 brightness. Tests quality analysis and low-light detection.",
            "limitation": "Synthetic uniform darkness â‰  real outdoor night footage. Results are PARTIALLY VALIDATED at best.",
        })
    return results


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXP-C: Fast motion â€” static + burst + static
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_exp_c():
    path = str(BASE_DIR / "fast_motion_60s.mp4")
    out = _make_writer(path)
    total = 60 * FPS
    for i in range(total):
        t = i / FPS
        frame = _noisy_bg(80)
        if t < 20:
            # Static: rectangle parked at left
            cx, cy = 200, H // 2
        elif t < 30:
            # Burst: rectangle sprints left â†’ right in 10s
            cx = int(200 + (W - 400) * ((t - 20) / 10))
            cy = H // 2
        else:
            # Static: rectangle parked at right
            cx, cy = W - 200, H // 2
        _draw_rect(frame, cx, cy, 80, 200)
        out.write(frame)
    out.release()
    print(f"  âœ“ {path}")
    return {
        "video_id": "exp_c_fast_motion",
        "path": path,
        "duration_s": 60,
        "description": "Static 20s â†’ fast motion 10s â†’ static 30s. Tests adaptive skip protection during burst.",
        "motion_burst_start_s": 20,
        "motion_burst_end_s": 30,
        "limitation": "Synthetic motion via pixel movement. MOG2 will detect pixel changes, not semantic content.",
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXP-D: Multi-person â€” 2 moving rectangles
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_exp_d():
    path = str(BASE_DIR / "multi_person_30s.mp4")
    out = _make_writer(path)
    total = 30 * FPS
    for i in range(total):
        t = i / FPS
        frame = _noisy_bg(80)
        # Person A: left to right
        cx_a = int(100 + (W * 0.4) * (t / 30))
        cy_a = H // 3
        _draw_rect(frame, cx_a, cy_a, 70, 180, (220, 220, 220))
        # Person B: right to left (opposite direction)
        cx_b = int(W - 100 - (W * 0.4) * (t / 30))
        cy_b = 2 * H // 3
        _draw_rect(frame, cx_b, cy_b, 70, 180, (200, 200, 200))
        out.write(frame)
    out.release()
    print(f"  âœ“ {path}")
    return {
        "video_id": "exp_d_multi_person",
        "path": path,
        "duration_s": 30,
        "description": "Two rectangles moving in opposite directions. Tests multi-track handling.",
        "limitation": "YOLO will not detect as 2 people. Tests track infrastructure, not detection.",
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXP-E: ROI crossing â€” enters zone at frame 375, exits at frame 625
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_exp_e():
    path = str(BASE_DIR / "roi_crossing_30s.mp4")
    out = _make_writer(path)
    # ROI zone: x=0.4-0.6 normalized = 768-1152 px
    zone_x1, zone_x2 = int(W * 0.4), int(W * 0.6)
    total = 30 * FPS
    for i in range(total):
        t = i / FPS
        frame = _noisy_bg(80)
        # Draw zone indicator
        cv2.rectangle(frame, (zone_x1, 0), (zone_x2, H), (0, 50, 0), 2)
        # Rectangle enters zone at t=15 (375 frames), exits at t=25 (625 frames)
        cx = int(100 + (W - 200) * (t / 30))
        cy = H // 2
        _draw_rect(frame, cx, cy, 80, 200)
        out.write(frame)
    out.release()
    print(f"  âœ“ {path}")
    return {
        "video_id": "exp_e_roi_crossing",
        "path": path,
        "duration_s": 30,
        "description": "Rectangle crosses ROI zone (x=0.4-0.6) at t=15s, exits at t=25s.",
        "zone_normalized": {"x1": 0.4, "y1": 0.0, "x2": 0.6, "y2": 1.0},
        "expected_entry_s": 15.0,
        "expected_exit_s": 25.0,
        "limitation": "ROI crossing logic is geometry-based. Will work even without YOLO detection if track data flows.",
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXP-G: Scaling â€” 30s, 60s, 5min, 10min, 30min
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_exp_g():
    scale_dir = BASE_DIR / "scaling"
    scale_dir.mkdir(exist_ok=True)
    configs = [
        ("scaling_30s", 30),
        ("scaling_60s", 60),
        ("scaling_5min", 300),
        ("scaling_10min", 600),
        ("scaling_30min", 1800),
    ]
    results = []
    for name, dur in configs:
        path = str(scale_dir / f"{name}.mp4")
        out = _make_writer(path)
        total = dur * FPS
        for i in range(total):
            t = i / FPS
            frame = _noisy_bg(80)
            # Slow periodic movement
            cx = int(W // 2 + (W // 4) * np.sin(2 * np.pi * t / 10))
            cy = H // 2
            _draw_rect(frame, cx, cy, 80, 200)
            out.write(frame)
        out.release()
        print(f"  âœ“ {path}  ({dur}s)")
        results.append({
            "video_id": f"exp_g_{name}",
            "path": path,
            "duration_s": dur,
            "resolution": f"{W}x{H}",
            "fps": FPS,
            "description": f"Scaling test: {dur}s video with periodic movement.",
        })
    return results


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# EXP-H: Pose sequence â€” standing â†’ crouching bbox â†’ crawling bbox
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def gen_exp_h():
    path = str(BASE_DIR / "pose_sequence_30s.mp4")
    out = _make_writer(path)
    total = 30 * FPS
    for i in range(total):
        t = i / FPS
        frame = _noisy_bg(80)
        cx = W // 2
        cy_center = 2 * H // 3  # near bottom of frame

        if t < 10:
            # Standing: tall narrow bbox (~30% frame height)
            rh = int(H * 0.30)
            rw = int(rh * 0.30)
            cy = cy_center - rh // 2
        elif t < 20:
            # Crouching: compressed bbox (~15% frame height, wider)
            rh = int(H * 0.15)
            rw = int(rh * 0.8)
            cy = cy_center
            # Gradual lowering during first 2s of crouching phase
            frac = min(1.0, (t - 10) / 2.0)
            rh = int(H * (0.30 - 0.15 * frac))
            rw = int(rh * (0.30 + 0.50 * frac))
        else:
            # Crawling: very low bbox + horizontal movement (~10% height, wide)
            rh = int(H * 0.10)
            rw = int(rh * 1.6)
            cx = int(W // 2 + (W // 4) * ((t - 20) / 10))  # slow lateral movement
            cy = cy_center + rh

        _draw_rect(frame, cx, cy, rw, rh)
        out.write(frame)
    out.release()
    print(f"  âœ“ {path}")
    return {
        "video_id": "exp_h_pose_sequence",
        "path": path,
        "duration_s": 30,
        "description": (
            "0-10s: standing bbox (30% height), "
            "10-20s: crouching bbox (15% height), "
            "20-30s: crawling bbox (10% height + lateral movement)"
        ),
        "expected_events": [
            {"type": "person_crouching_sustained", "start_s": 12, "end_s": 20},
            {"type": "person_crawling", "start_s": 22, "end_s": 30},
        ],
        "limitation": (
            "Bbox geometry, not real body. TemporalPoseAnalyzer thresholds were "
            "designed for normalised bboxes. This tests the state machine logic, "
            "not real human pose detection."
        ),
    }


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main():
    t0 = time.perf_counter()
    print(f"Generating Phase 4 validation corpus in: {BASE_DIR}")
    print(f"  Resolution: {W}x{H} @ {FPS}fps")
    print()

    manifest = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "videos": []}

    print("[EXP-A] Normal light walking 60s...")
    manifest["videos"].append(gen_exp_a())

    print("[EXP-B] Low-light 4 levels...")
    manifest["videos"].extend(gen_exp_b())

    print("[EXP-C] Fast motion burst 60s...")
    manifest["videos"].append(gen_exp_c())

    print("[EXP-D] Multi-person 30s...")
    manifest["videos"].append(gen_exp_d())

    print("[EXP-E] ROI crossing 30s...")
    manifest["videos"].append(gen_exp_e())

    print("[EXP-G] Scaling 30s â†’ 30min...")
    manifest["videos"].extend(gen_exp_g())

    print("[EXP-H] Pose sequence 30s...")
    manifest["videos"].append(gen_exp_h())

    # Write manifest
    mpath = BASE_DIR / "manifest.json"
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n  âœ“ Manifest: {mpath}")

    elapsed = time.perf_counter() - t0
    print(f"\nCorpus generated in {elapsed:.1f}s ({len(manifest['videos'])} videos)")
    print()
    print("NOTE: These are synthetic videos.")
    print("YOLO11x will not detect rectangles as persons.")
    print("Detection accuracy experiments require real footage.")
    print("These videos test: extraction, quality, ROI geometry, adaptive skip, scaling.")


if __name__ == "__main__":
    main()

