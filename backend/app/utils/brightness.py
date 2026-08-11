"""
Brightness Analyzer — Scene-level illumination change detection.

Detects lighting events (lights on / lights off) purely from pixel
luminosity analysis of extracted frames. No ML model required.

Algorithm (v2 — windowed baseline):
  1. Compute mean luminance of each frame (RGB → Grayscale → mean pixel)
  2. Apply median smoothing (window=5) to remove JPEG noise
  3. Compute a ROLLING BASELINE (median of past 2 seconds of frames)
     instead of comparing consecutive frames. This is more robust:
     - Frame-to-frame delta misses slow gradual changes and also
       reacts to any single noisy frame.
     - Rolling baseline delta detects sustained changes only.
  4. Detect when the current frame deviates from the baseline by
     more than `brightness_threshold` for at least 2 consecutive frames
     (prevents single-frame noise from firing events)
  5. Merge events within `merge_gap_ms` to avoid double-firing

Why windowed baseline is better for indoor lighting:
    Window-based approach: "Was this room darker/brighter 2 seconds ago?"
    This reliably catches ceiling light toggles even in rooms with strong
    natural window light, where the absolute change may be small relative
    to the total brightness but the DELTA from the recent baseline is clear.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FrameBrightness:
    """Brightness measurement for a single frame."""
    frame_number: int
    timestamp_ms: float
    frame_path: str
    raw_brightness: float       # 0-255, mean pixel luminance
    smoothed_brightness: float  # After median smoothing
    baseline_brightness: float = 0.0  # Rolling 2s median
    delta_from_baseline: float = 0.0  # How far from recent baseline


@dataclass
class LightingEvent:
    """
    A detected lighting transition event.

    event_type:  "light_turned_on" or "light_turned_off"
    frame_number: Frame where transition was detected.
    timestamp_ms: Timestamp in milliseconds.
    brightness_before: Smoothed brightness before transition.
    brightness_after:  Smoothed brightness after transition.
    delta:        Signed brightness change (positive = brighter).
    confidence:   [0.0, 1.0] — scales with magnitude of change.
    """
    frame_number: int
    timestamp_ms: float
    event_type: str           # "light_turned_on" | "light_turned_off"
    brightness_before: float
    brightness_after: float
    delta: float
    confidence: float
    evidence: dict = field(default_factory=dict)


def _compute_mean_brightness(frame_path: str) -> Optional[float]:
    """
    Return mean luminance [0, 255] for a single frame image.

    Converts to grayscale (ITU-R 601 weighting) before computing mean.
    Returns None if the file cannot be read.
    """
    try:
        from PIL import Image
        import numpy as np
        with Image.open(frame_path) as img:
            gray = img.convert("L")
            arr = np.array(gray, dtype=np.float32)
            return float(arr.mean())
    except Exception as exc:
        logger.debug("Could not read brightness from %s: %s", frame_path, exc)
        return None


def _median_smooth(values: list[float], window: int = 5) -> list[float]:
    """Apply median filter with given window size."""
    if window < 1:
        return list(values)
    half = window // 2
    smoothed = []
    n = len(values)
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        smoothed.append(statistics.median(values[start:end]))
    return smoothed


def _rolling_baseline(
    values: list[float],
    timestamps_ms: list[float],
    window_ms: float = 2000.0,
) -> list[float]:
    """
    Compute a rolling median baseline for each position.

    For position i, the baseline is the median of all smoothed brightness
    values in the window [timestamps[i] - window_ms, timestamps[i]].
    This gives a "what was the brightness recently?" reference.

    Uses the frame immediately before i (not including i itself) to
    avoid the current frame affecting its own baseline.
    """
    baseline = []
    n = len(values)
    for i in range(n):
        t_now = timestamps_ms[i]
        t_min = t_now - window_ms
        # Collect past values (not including current frame)
        past = [values[j] for j in range(i) if timestamps_ms[j] >= t_min]
        if not past:
            # First few frames — use global median of first 10 frames as init
            baseline.append(statistics.median(values[:min(10, n)]))
        else:
            baseline.append(statistics.median(past))
    return baseline


def analyze_frames(
    frame_paths: list[str],
    frame_numbers: list[int],
    timestamps_ms: list[float],
    baseline_window_ms: float = 2000.0,
) -> list[FrameBrightness]:
    """
    Compute brightness for every frame and return the sequence.

    Args:
        frame_paths:        Absolute paths to extracted frame images.
        frame_numbers:      Corresponding frame numbers (for timestamps).
        timestamps_ms:      Corresponding timestamps in milliseconds.
        baseline_window_ms: Rolling baseline window size (default 2s).

    Returns:
        List of FrameBrightness objects with smoothed + baseline values.
    """
    if not frame_paths:
        return []

    raw: list[float] = []
    last_valid = 128.0
    for path in frame_paths:
        b = _compute_mean_brightness(path)
        if b is not None:
            last_valid = b
        raw.append(last_valid)

    smoothed = _median_smooth(raw, window=5)
    baseline = _rolling_baseline(smoothed, timestamps_ms, window_ms=baseline_window_ms)

    result = []
    for i, (path, fn, ts) in enumerate(zip(frame_paths, frame_numbers, timestamps_ms)):
        delta = smoothed[i] - baseline[i]
        result.append(FrameBrightness(
            frame_number=fn,
            timestamp_ms=ts,
            frame_path=path,
            raw_brightness=round(raw[i], 2),
            smoothed_brightness=round(smoothed[i], 2),
            baseline_brightness=round(baseline[i], 2),
            delta_from_baseline=round(delta, 2),
        ))

    # Log brightness stats for debugging
    if raw:
        logger.info(
            "Brightness analysis: min=%.1f, max=%.1f, mean=%.1f, range=%.1f "
            "across %d frames",
            min(raw), max(raw), sum(raw)/len(raw), max(raw)-min(raw), len(raw),
        )

    return result


def detect_lighting_events(
    frame_brightnesses: list[FrameBrightness],
    brightness_threshold: float = 10.0,
    merge_gap_ms: float = 800.0,
    min_consecutive: int = 2,
) -> list[LightingEvent]:
    """
    Detect light-on / light-off events using windowed baseline comparison.

    An event fires when:
    - The frame's brightness deviates from its rolling baseline by more
      than `brightness_threshold` for at least `min_consecutive` frames.
    - This ignores single-frame noise (JPEG artifacts, reflections).

    Args:
        frame_brightnesses: Output of analyze_frames().
        brightness_threshold: Minimum delta from 2s baseline to count as event.
            Default 10.0: catches indoor ceiling lights even in bright rooms.
        merge_gap_ms: Merge same-type events closer than this.
        min_consecutive: Minimum frames deviation must persist before firing.

    Returns:
        List of LightingEvent, sorted by timestamp_ms.
    """
    if len(frame_brightnesses) < 4:
        return []

    raw_events: list[LightingEvent] = []
    n = len(frame_brightnesses)

    # State tracking for consecutive detection
    consecutive_up = 0
    consecutive_down = 0
    pending_up_start: int | None = None
    pending_down_start: int | None = None

    for i, fb in enumerate(frame_brightnesses):
        delta = fb.delta_from_baseline

        if delta >= brightness_threshold:
            consecutive_up += 1
            consecutive_down = 0
            if pending_up_start is None:
                pending_up_start = i
            if consecutive_up >= min_consecutive and pending_up_start is not None:
                # Fire light_turned_on event at the START of the deviation
                start_fb = frame_brightnesses[pending_up_start]
                baseline = start_fb.baseline_brightness
                confidence = min(0.97, 0.55 + abs(delta) / (brightness_threshold * 4) * 0.42)
                raw_events.append(LightingEvent(
                    frame_number=start_fb.frame_number,
                    timestamp_ms=start_fb.timestamp_ms,
                    event_type="light_turned_on",
                    brightness_before=round(baseline, 2),
                    brightness_after=round(fb.smoothed_brightness, 2),
                    delta=round(delta, 2),
                    confidence=round(confidence, 4),
                    evidence={
                        "brightness_before": round(baseline, 2),
                        "brightness_after": round(fb.smoothed_brightness, 2),
                        "delta_from_baseline": round(delta, 2),
                        "threshold": brightness_threshold,
                        "consecutive_frames": consecutive_up,
                        "method": "windowed_baseline",
                    },
                ))
                pending_up_start = None  # Reset — don't re-fire
                consecutive_up = 0

        elif delta <= -brightness_threshold:
            consecutive_down += 1
            consecutive_up = 0
            if pending_down_start is None:
                pending_down_start = i
            if consecutive_down >= min_consecutive and pending_down_start is not None:
                start_fb = frame_brightnesses[pending_down_start]
                baseline = start_fb.baseline_brightness
                confidence = min(0.97, 0.55 + abs(delta) / (brightness_threshold * 4) * 0.42)
                raw_events.append(LightingEvent(
                    frame_number=start_fb.frame_number,
                    timestamp_ms=start_fb.timestamp_ms,
                    event_type="light_turned_off",
                    brightness_before=round(baseline, 2),
                    brightness_after=round(fb.smoothed_brightness, 2),
                    delta=round(delta, 2),
                    confidence=round(confidence, 4),
                    evidence={
                        "brightness_before": round(baseline, 2),
                        "brightness_after": round(fb.smoothed_brightness, 2),
                        "delta_from_baseline": round(delta, 2),
                        "threshold": brightness_threshold,
                        "consecutive_frames": consecutive_down,
                        "method": "windowed_baseline",
                    },
                ))
                pending_down_start = None
                consecutive_down = 0
        else:
            # Back to baseline — reset all counters
            consecutive_up = 0
            consecutive_down = 0
            pending_up_start = None
            pending_down_start = None

    # Merge nearby same-type events
    merged = _merge_events(raw_events, merge_gap_ms)
    logger.info(
        "Lighting events: %d raw → %d merged (threshold=%.1f, min_consecutive=%d)",
        len(raw_events), len(merged), brightness_threshold, min_consecutive,
    )
    return merged


def _merge_events(events: list[LightingEvent], gap_ms: float) -> list[LightingEvent]:
    """Merge consecutive same-type events within gap_ms into one."""
    if not events:
        return []
    merged = [events[0]]
    for evt in events[1:]:
        prev = merged[-1]
        if (evt.event_type == prev.event_type
                and evt.timestamp_ms - prev.timestamp_ms <= gap_ms):
            if evt.confidence > prev.confidence:
                merged[-1] = evt
        else:
            merged.append(evt)
    return merged
