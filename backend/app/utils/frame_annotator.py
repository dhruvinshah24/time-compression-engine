"""
Annotated Frame Generator — TCE Accuracy Overhaul v1.0.1.

Draws detection bounding boxes, track IDs, confidence scores, ROI zone overlays,
event labels, and timestamps onto real video frames.

Used by S12 to generate:
  1. Event thumbnails — the actual frame from the video with annotations
  2. Before/event/after frames — for the event preview modal in the UI
  3. Full annotated frames stored in outputs/jobs/{JOB_ID}/annotated/

Why this matters (from the overhaul spec):
  "When I click an event: I should immediately see the ACTUAL video frame.
   No blank preview. No fake placeholder. No generic image."
  "Do not create fake graphics. Generate them from real detection data."

Design:
  - All drawing uses OpenCV (no external deps beyond numpy+cv2).
  - Colors are deterministic per class name (hash-based palette).
  - Track ID labels are always readable (white text, dark background).
  - ROI zones are drawn as semi-transparent polygon overlays.
  - If the frame file does not exist, raises FileNotFoundError (caller handles).
  - Output files are saved as JPEG (quality=90) for reasonable file size.

Branch: experiment/v1.0.1-accuracy-overhaul
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional, Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Color palette (deterministic, hash-based per class name)
# ---------------------------------------------------------------------------

# Hardcoded colors for most common classes
_CLASS_COLORS: dict[str, tuple[int, int, int]] = {
    "person":     (0, 200, 0),      # Green
    "car":        (0, 120, 255),    # Orange-blue
    "truck":      (0, 80, 200),     # Darker blue
    "bicycle":    (255, 180, 0),    # Gold
    "motorcycle": (255, 100, 0),    # Orange
    "backpack":   (200, 0, 200),    # Purple
    "suitcase":   (150, 0, 150),    # Dark purple
    "handbag":    (180, 0, 180),    # Purple-pink
    "cell phone": (0, 255, 255),    # Cyan
    "laptop":     (0, 200, 255),    # Light blue
    "bottle":     (100, 255, 100),  # Light green
    "chair":      (200, 200, 0),    # Yellow
    "couch":      (180, 180, 0),    # Dark yellow
    "default":    (180, 180, 180),  # Gray
}


def _class_color(class_name: str) -> tuple[int, int, int]:
    """Return a deterministic BGR color for a class name."""
    if class_name.lower() in _CLASS_COLORS:
        return _CLASS_COLORS[class_name.lower()]
    h = int(hashlib.md5(class_name.encode()).hexdigest()[:6], 16)
    r = (h & 0xFF0000) >> 16
    g = (h & 0x00FF00) >> 8
    b = h & 0x0000FF
    # Ensure readable (avoid very dark colors)
    r, g, b = max(r, 80), max(g, 80), max(b, 80)
    return (b, g, r)  # OpenCV is BGR


# ---------------------------------------------------------------------------
# Core annotation function
# ---------------------------------------------------------------------------

def annotate_frame(
    frame_bgr: np.ndarray,
    detections: Optional[list[Any]] = None,
    tracks: Optional[list[Any]] = None,
    roi_zones: Optional[list[dict]] = None,
    event_label: Optional[str] = None,
    event_confidence: Optional[float] = None,
    timestamp_ms: Optional[float] = None,
    draw_track_ids: bool = True,
    draw_confidence: bool = True,
    draw_timestamp: bool = True,
) -> np.ndarray:
    """
    Draw annotations onto a BGR frame and return the annotated copy.

    Draws (if provided):
      - Detection bounding boxes with class names + confidence
      - Track IDs (if tracks is provided)
      - ROI zone polygon overlays (semi-transparent)
      - Event label at the bottom of the frame
      - Timestamp in the top-left corner

    Args:
        frame_bgr:         OpenCV BGR frame (uint8 numpy array).
        detections:        List of Detection objects (from model_registry.base_model).
                           Each must have: bbox_norm, class_name, confidence.
        tracks:            List of Track objects (from engines.perception.tracker.track).
                           Each must have: track_id, observations[-1].bbox.
        roi_zones:         List of zone dicts with 'polygon' [[x,y], ...] and 'name'.
        event_label:       Text to display at the bottom (e.g., "Restricted Zone Entry").
        event_confidence:  Confidence to show next to event label.
        timestamp_ms:      Frame timestamp in milliseconds (shown as HH:MM:SS.mmm).
        draw_track_ids:    Whether to draw track ID labels.
        draw_confidence:   Whether to draw confidence values on boxes.
        draw_timestamp:    Whether to draw timestamp in top-left.

    Returns:
        Annotated BGR numpy array (same shape as input).
    """
    try:
        import cv2
    except ImportError:
        logger.warning("[Annotator] OpenCV not available — returning raw frame")
        return frame_bgr.copy()

    frame = frame_bgr.copy()
    h, w = frame.shape[:2]

    # ── Draw ROI zones (semi-transparent polygons) ─────────────────────────
    if roi_zones:
        overlay = frame.copy()
        for zone_cfg in roi_zones:
            poly = zone_cfg.get("polygon", [])
            if len(poly) < 3:
                continue
            pts = np.array(
                [[int(p[0] * w), int(p[1] * h)] for p in poly],
                dtype=np.int32,
            )
            # Fill semi-transparent
            cv2.fillPoly(overlay, [pts], (0, 0, 180))
        # Blend overlay with alpha=0.25
        cv2.addWeighted(overlay, 0.25, frame, 0.75, 0, frame)

        # Draw zone borders
        for zone_cfg in roi_zones:
            poly = zone_cfg.get("polygon", [])
            if len(poly) < 3:
                continue
            pts = np.array(
                [[int(p[0] * w), int(p[1] * h)] for p in poly],
                dtype=np.int32,
            )
            cv2.polylines(frame, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
            # Zone label near first vertex
            label = zone_cfg.get("name", "Zone")
            px, py = pts[0]
            _draw_label(frame, label, px, py - 8, (0, 0, 255), cv2)

    # ── Draw detection bounding boxes ──────────────────────────────────────
    if detections:
        for det in detections:
            try:
                bbox = getattr(det, "bbox_norm", None) or getattr(det, "bbox", None)
                if bbox is None:
                    continue
                x1 = int(bbox[0] * w)
                y1 = int(bbox[1] * h)
                x2 = int(bbox[2] * w)
                y2 = int(bbox[3] * h)
                cls = getattr(det, "class_name", "object")
                conf = getattr(det, "confidence", 0.0)
                color = _class_color(cls)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                if draw_confidence:
                    label = f"{cls} {conf:.2f}"
                else:
                    label = cls
                _draw_label(frame, label, x1, y1 - 8, color, cv2)
            except Exception:
                continue

    # ── Draw track bounding boxes + IDs ───────────────────────────────────
    if tracks and draw_track_ids:
        for track in tracks:
            try:
                obs_list = getattr(track, "observations", [])
                if not obs_list:
                    continue
                last_obs = obs_list[-1]
                bbox = getattr(last_obs, "bbox", None)
                if bbox is None:
                    continue
                x1 = int(bbox[0] * w)
                y1 = int(bbox[1] * h)
                x2 = int(bbox[2] * w)
                y2 = int(bbox[3] * h)
                tid = getattr(track, "track_id", "?")
                person_label = getattr(track, "person_label", None)
                label = person_label or f"Track {tid}"
                color = (0, 230, 0)  # Bright green for tracks
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                _draw_label(frame, label, x1, y1 - 8, color, cv2)
            except Exception:
                continue

    # ── Timestamp (top-left) ──────────────────────────────────────────────
    if draw_timestamp and timestamp_ms is not None:
        ts = _ms_to_hms(timestamp_ms)
        cv2.putText(
            frame, ts, (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 3, cv2.LINE_AA,
        )
        cv2.putText(
            frame, ts, (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, cv2.LINE_AA,
        )

    # ── Event label (bottom center) ───────────────────────────────────────
    if event_label:
        text = event_label
        if event_confidence is not None:
            text = f"{event_label}  {event_confidence*100:.0f}%"
        text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)[0]
        tx = max(0, (w - text_size[0]) // 2)
        ty = h - 20
        # Background rectangle
        cv2.rectangle(frame, (tx - 8, ty - text_size[1] - 8), (tx + text_size[0] + 8, ty + 8), (0, 0, 0), -1)
        cv2.putText(
            frame, text, (tx, ty),
            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2, cv2.LINE_AA,
        )

    return frame


def _draw_label(frame: np.ndarray, text: str, x: int, y: int, color: tuple, cv2) -> None:
    """Draw a text label with dark background at (x, y)."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    thickness = 1
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    px = max(0, x)
    py = max(th + 4, y)
    cv2.rectangle(frame, (px - 2, py - th - 4), (px + tw + 2, py + 2), (0, 0, 0), -1)
    cv2.putText(frame, text, (px, py), font, scale, color, thickness, cv2.LINE_AA)


def _ms_to_hms(ms: float) -> str:
    """Convert milliseconds to HH:MM:SS.mmm string."""
    total_s = int(ms / 1000)
    millis = int(ms % 1000)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"


# ---------------------------------------------------------------------------
# Event thumbnail generation
# ---------------------------------------------------------------------------

def generate_event_thumbnail(
    frame_path: str,
    event_type: str,
    event_confidence: float,
    timestamp_ms: float,
    output_path: str,
    bbox_norm: Optional[list[float]] = None,
    track_label: Optional[str] = None,
    roi_zones: Optional[list[dict]] = None,
    max_width: int = 640,
) -> str:
    """
    Generate an annotated thumbnail image for an event.

    Opens the actual video frame from disk, draws the event bounding box,
    event label, track ID, and timestamp, then saves to output_path.

    Args:
        frame_path:        Absolute path to the extracted frame JPEG.
        event_type:        Event type string (e.g., 'restricted_zone_entry').
        event_confidence:  Event confidence [0, 1].
        timestamp_ms:      Frame timestamp.
        output_path:       Where to save the annotated thumbnail.
        bbox_norm:         Optional [x1, y1, x2, y2] in [0,1] for the event bbox.
        track_label:       Optional label like 'Person 1' or 'Track 17'.
        roi_zones:         Optional list of zone configs to overlay.
        max_width:         Resize thumbnail to this max width (0 = no resize).

    Returns:
        Absolute path to the saved thumbnail.

    Raises:
        FileNotFoundError: If frame_path does not exist.
    """
    import cv2

    if not Path(frame_path).exists():
        raise FileNotFoundError(f"Frame not found: {frame_path}")

    frame = cv2.imread(frame_path)
    if frame is None:
        raise FileNotFoundError(f"Could not decode frame: {frame_path}")

    h, w = frame.shape[:2]

    # Optionally resize for smaller thumbnails
    if max_width > 0 and w > max_width:
        scale = max_width / w
        frame = cv2.resize(frame, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]

    # Build a simple detection list from the event's bbox
    class _FakeDet:
        def __init__(self, bbox, label, conf):
            self.bbox_norm = bbox
            self.class_name = label
            self.confidence = conf

    detections = []
    if bbox_norm is not None:
        label = track_label or event_type.replace("_", " ").title()
        detections.append(_FakeDet(bbox_norm, label, event_confidence))

    # Format event label
    display_label = event_type.replace("_", " ").upper()

    frame = annotate_frame(
        frame_bgr=frame,
        detections=detections if detections else None,
        roi_zones=roi_zones,
        event_label=display_label,
        event_confidence=event_confidence,
        timestamp_ms=timestamp_ms,
        draw_track_ids=False,
        draw_confidence=True,
        draw_timestamp=True,
    )

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Save as JPEG
    success = cv2.imwrite(output_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        raise IOError(f"Failed to save thumbnail to: {output_path}")

    logger.debug("[Annotator] Saved thumbnail: %s", output_path)
    return output_path


def generate_before_event_after(
    frame_paths: list[str],
    frame_numbers: list[int],
    event_frame: int,
    event_type: str,
    event_confidence: float,
    output_dir: str,
    event_id: str,
    timestamps_ms: Optional[list[float]] = None,
    pre_post_count: int = 1,
) -> dict[str, Optional[str]]:
    """
    Generate before/event/after thumbnail frames for an event preview.

    Finds the closest frames to the event frame number, annotates them,
    and saves them to output_dir.

    Args:
        frame_paths:    All extracted frame paths.
        frame_numbers:  Corresponding frame numbers.
        event_frame:    Frame number of the event.
        event_type:     Event type string.
        event_confidence: Event confidence.
        output_dir:     Directory to save the thumbnails.
        event_id:       Unique event ID (used in filenames).
        timestamps_ms:  Optional timestamps for each frame.
        pre_post_count: How many frames before/after to include (default 1).

    Returns:
        Dict with keys 'before', 'event', 'after' mapping to saved file paths
        (or None if the corresponding frame was not found).
    """
    result: dict[str, Optional[str]] = {"before": None, "event": None, "after": None}

    if not frame_paths or not frame_numbers:
        return result

    # Find the index closest to event_frame
    event_idx = min(range(len(frame_numbers)), key=lambda i: abs(frame_numbers[i] - event_frame))

    roles = {
        "before": max(0, event_idx - pre_post_count),
        "event":  event_idx,
        "after":  min(len(frame_numbers) - 1, event_idx + pre_post_count),
    }

    for role, idx in roles.items():
        fpath = frame_paths[idx]
        ts = timestamps_ms[idx] if timestamps_ms else 0.0
        out_path = str(Path(output_dir) / f"{event_id}_{role}.jpg")
        label = event_type.replace("_", " ").upper() if role == "event" else None
        conf = event_confidence if role == "event" else None

        try:
            import cv2
            frame = cv2.imread(fpath)
            if frame is None:
                continue
            annotated = annotate_frame(
                frame_bgr=frame,
                event_label=label,
                event_confidence=conf,
                timestamp_ms=ts,
            )
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(out_path, annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
            result[role] = out_path
        except Exception as exc:
            logger.warning("[Annotator] Could not generate %s frame for event %s: %s", role, event_id, exc)

    return result
