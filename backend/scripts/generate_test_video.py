"""
Generate a synthetic test video for TCE end-to-end testing.

Creates a 45-second video at 1080p 25fps with:
- Moving bright rectangle (simulates person walking)
- Two zone crossings (left→center→right)  
- One stationary pause (simulates loitering)
- Lighting change (frame 400-450 dimmed to simulate low light)
- Dark frames (frames 600-650 near-black to test UNUSABLE detection)

Output: outputs/test/synthetic_test.mp4
"""

import cv2
import numpy as np
import os
from pathlib import Path

OUTPUT_DIR = Path("outputs/test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = str(OUTPUT_DIR / "synthetic_test.mp4")

# Video params
FPS = 25
DURATION_S = 45
TOTAL_FRAMES = FPS * DURATION_S
W, H = 1920, 1080

print(f"Generating synthetic test video: {TOTAL_FRAMES} frames @ {FPS}fps, {W}x{H}")

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = cv2.VideoWriter(OUTPUT_PATH, fourcc, FPS, (W, H))

if not writer.isOpened():
    raise RuntimeError(f"Could not open VideoWriter for {OUTPUT_PATH}")

RECT_W, RECT_H = 80, 200  # Simulated "person" bounding box

for frame_idx in range(TOTAL_FRAMES):
    t = frame_idx / FPS  # seconds

    # Base background — slightly noisy gray
    bg = np.full((H, W, 3), 80, dtype=np.uint8)
    noise = np.random.randint(-8, 8, (H, W, 3), dtype=np.int16)
    bg = np.clip(bg.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Moving rectangle trajectory:
    # 0-10s: enters from left, walks to center
    # 10-20s: pauses at center (loitering simulation)
    # 20-30s: walks to right
    # 30-35s: exits right edge
    # 35-40s: re-enters from left
    # 40-45s: exits bottom
    if t < 10:
        cx = int(50 + (W * 0.45 - 50) * (t / 10))
        cy = H // 2
    elif t < 20:
        cx = W // 2
        cy = H // 2
    elif t < 30:
        cx = int(W * 0.5 + (W * 0.45 - 50) * ((t - 20) / 10))
        cy = H // 2
    elif t < 35:
        cx = W - 30
        cy = H // 2
    elif t < 40:
        cx = int(50 + (W * 0.4 - 50) * ((t - 35) / 5))
        cy = H // 2
    else:
        cx = W // 3
        cy = int(H // 2 + (H // 2 - 50) * ((t - 40) / 5))

    # Draw person rectangle (bright white)
    x1 = max(0, cx - RECT_W // 2)
    y1 = max(0, cy - RECT_H // 2)
    x2 = min(W, cx + RECT_W // 2)
    y2 = min(H, cy + RECT_H // 2)

    # Lighting change: frames 400-450 (16-18s) very dark
    if 400 <= frame_idx <= 450:
        bg = np.clip(bg * 0.15, 0, 255).astype(np.uint8)  # Very dark (low-light test)

    # Dark/unusable frames: 600-650 (24-26s) near-black
    elif 600 <= frame_idx <= 650:
        bg = np.full((H, W, 3), 3, dtype=np.uint8)  # Near black (UNUSABLE test)
    
    # Normal lighting restored after 650
    
    # Draw rectangle (person simulation)
    if frame_idx < 600 or frame_idx > 650:
        cv2.rectangle(bg, (x1, y1), (x2, y2), (220, 220, 220), -1)
        # Add "head" circle
        cv2.circle(bg, (cx, max(y1 - 15, 15)), 18, (200, 200, 200), -1)

    # Add timestamp text
    ts_text = f"t={t:.1f}s frame={frame_idx}"
    cv2.putText(bg, ts_text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)

    # Add zone lines (visual reference)
    cv2.line(bg, (W // 3, 0), (W // 3, H), (100, 100, 150), 2)
    cv2.line(bg, (2 * W // 3, 0), (2 * W // 3, H), (100, 100, 150), 2)

    writer.write(bg)

    if frame_idx % 250 == 0:
        print(f"  Frame {frame_idx}/{TOTAL_FRAMES} ({100*frame_idx//TOTAL_FRAMES}%)")

writer.release()
print(f"\nSynthetic test video written to: {OUTPUT_PATH}")
print(f"Size: {Path(OUTPUT_PATH).stat().st_size / 1024 / 1024:.1f} MB")
print(f"Duration: {DURATION_S}s | Frames: {TOTAL_FRAMES} | {W}x{H}@{FPS}fps")
print("\nExpected pipeline behavior:")
print("  - QUICK_TEST profile (<=30s... actually SHORT at 45s)")
print("  - Frames 400-450: LOW_LIGHT/VERY_LOW_LIGHT → CLAHE enhancement")
print("  - Frames 600-650: UNUSABLE → skipped (0 detections expected)")
print("  - Moving rectangle should generate: person_entered_scene, person_walking,")
print("    person_loitering (10-20s pause), person_left_scene")
