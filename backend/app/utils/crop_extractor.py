"""
Crop Extractor — extracts and saves person crops from video frames.

For each confirmed person track, we save the highest-confidence crop as
a JPEG thumbnail. These crops:
  1. Feed into the ReID engine (AppearanceEmbedder).
  2. Appear in the frontend timeline as person thumbnails.

Design:
  - Crops are saved to: outputs/{job_id}/crops/person_{label}_{frame}.jpg
  - Only the best crop per person label is kept (highest detection confidence).
  - Minimum crop size enforced to discard tiny/distant detections.
  - Frame images are loaded lazily (only load a frame if a person was seen in it).

This module is I/O bound (disk reads/writes) not compute bound.
All paths are absolute. No path construction in caller code.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
MIN_CROP_WIDTH  = 20   # pixels — lowered from 32; captures distant people
MIN_CROP_HEIGHT = 40   # pixels — lowered from 64; captures small detections
CROP_QUALITY    = 92   # JPEG quality (increased for better ReID features)
PERSON_CLASSES  = {"person", "man", "woman", "child", "baby"}


def extract_person_crop(
    frame_bgr: np.ndarray,
    bbox_x1: float,
    bbox_y1: float,
    bbox_x2: float,
    bbox_y2: float,
) -> Optional[np.ndarray]:
    """
    Extract a person crop from a frame using normalised bbox coordinates.

    Args:
        frame_bgr: Full frame as (H, W, 3) BGR numpy array.
        bbox_x1, bbox_y1, bbox_x2, bbox_y2: Normalised [0, 1] coordinates.

    Returns:
        Cropped BGR numpy array, or None if too small.
    """
    h, w = frame_bgr.shape[:2]

    # Convert normalised → pixel coords
    px1 = max(0, int(bbox_x1 * w))
    py1 = max(0, int(bbox_y1 * h))
    px2 = min(w, int(bbox_x2 * w))
    py2 = min(h, int(bbox_y2 * h))

    cw = px2 - px1
    ch = py2 - py1

    if cw < MIN_CROP_WIDTH or ch < MIN_CROP_HEIGHT:
        return None

    return frame_bgr[py1:py2, px1:px2].copy()


def load_frame(frame_path: str) -> Optional[np.ndarray]:
    """Load a frame image from disk. Returns None on failure."""
    try:
        img = cv2.imread(str(frame_path))
        if img is None:
            logger.debug("[CropExtractor] Failed to load frame: %s", frame_path)
        return img
    except Exception as exc:  # noqa: BLE001
        logger.debug("[CropExtractor] Error loading %s: %s", frame_path, exc)
        return None


def extract_and_save_crops(
    frame_paths: dict[int, str],      # frame_number → absolute path
    all_tracks: list,                  # list of Track objects
    output_dir: str,
    embedder,                          # AppearanceEmbedder instance
    gallery,                           # PersonGallery instance
) -> dict[str, str]:
    """
    Process all confirmed person tracks, extract crops, run ReID, assign labels.

    For each person track:
      1. Find the observation with highest detection confidence.
      2. Load that frame from disk.
      3. Extract person crop.
      4. Run AppearanceEmbedder to get appearance embedding.
      5. Match against PersonGallery → get "Person N" label.
      6. Save crop JPEG to disk.
      7. Store crop path in gallery.

    Args:
        frame_paths:   Mapping from frame_number to path string.
        all_tracks:    All Track objects from the tracker.
        output_dir:    Root output directory (absolute).
        embedder:      AppearanceEmbedder instance.
        gallery:       PersonGallery instance.

    Returns:
        Mapping from track_id → person_label for all processed person tracks.
    """
    crops_dir = Path(output_dir) / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    track_to_label: dict[int, str] = {}   # track_id → "Person N"
    frame_cache: dict[int, Optional[np.ndarray]] = {}  # avoid reloading

    # Process all person tracks
    person_tracks = [
        t for t in all_tracks
        if t.class_name.lower() in PERSON_CLASSES and t.is_confirmed
    ]

    logger.info(
        "[CropExtractor] Processing %d person tracks for ReID",
        len(person_tracks),
    )

    for track in sorted(person_tracks, key=lambda t: t.created_timestamp_ms):
        if not track.observations:
            continue

        # Find best (highest confidence) observation
        best_obs = max(track.observations, key=lambda o: o.detection_confidence)
        frame_num = best_obs.frame_number

        # Compute entry direction from first observation
        first_obs = track.observations[0]
        entry_dir = _get_entry_direction(first_obs.bbox)

        # Load frame (cached)
        if frame_num not in frame_cache:
            path = frame_paths.get(frame_num)
            frame_cache[frame_num] = load_frame(path) if path else None
        frame_bgr = frame_cache[frame_num]

        # Extract crop
        crop = None
        if frame_bgr is not None:
            crop = extract_person_crop(
                frame_bgr,
                best_obs.bbox.x1,
                best_obs.bbox.y1,
                best_obs.bbox.x2,
                best_obs.bbox.y2,
            )

        # Compute embedding — skip track if crop unavailable
        if crop is None:
            logger.debug(
                "[CropExtractor] No valid crop for track %d (frame %d) — "
                "assigning sequential label without embedding",
                track.track_id, frame_num,
            )
            # Assign next sequential person label (don't run through gallery)
            existing = set(track_to_label.values())
            pid = 1
            while f"Person {pid}" in existing:
                pid += 1
            label = f"Person {pid}"
            track_to_label[track.track_id] = label
            track.person_label = label
            continue

        embedding = embedder.compute(crop)

        # Match/register in gallery
        label = gallery.match_or_register(
            crop_bgr=crop,
            track_id=track.track_id,
            timestamp_ms=first_obs.timestamp_ms,
            entry_direction=entry_dir,
        )

        # Save crop JPEG
        if crop is not None:
            safe_label = label.replace(" ", "_").lower()
            crop_filename = f"{safe_label}_t{track.track_id}_f{frame_num}.jpg"
            crop_path = crops_dir / crop_filename
            try:
                cv2.imwrite(
                    str(crop_path),
                    crop,
                    [cv2.IMWRITE_JPEG_QUALITY, CROP_QUALITY],
                )
                gallery.set_crop_path(label, str(crop_path))
                logger.debug("[CropExtractor] Saved crop: %s", crop_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[CropExtractor] Failed to save crop: %s", exc)

        track_to_label[track.track_id] = label
        # Store label on track object itself for downstream use
        track.person_label = label
        track.entry_direction = entry_dir

    # Compute exit direction for ended tracks
    for track in person_tracks:
        if track.observations:
            last_obs = track.observations[-1]
            exit_dir = _get_exit_direction(last_obs.bbox)
            track.exit_direction = exit_dir

    logger.info(
        "[CropExtractor] ReID complete: %d person labels assigned",
        len(set(track_to_label.values())),
    )
    return track_to_label


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_entry_direction(bbox) -> str:
    """
    Determine which edge of the frame a person entered from.

    Uses the centre of their bounding box in their first observation.
    Normalised coordinates [0, 1]: (0,0) is top-left, (1,1) is bottom-right.
    """
    cx, cy = bbox.cx, bbox.cy
    dist = {
        "left":   cx,
        "right":  1.0 - cx,
        "top":    cy,
        "bottom": 1.0 - cy,
    }
    return min(dist, key=dist.get)


def _get_exit_direction(bbox) -> str:
    """Determine which edge of the frame a person exited to."""
    cx, cy = bbox.cx, bbox.cy
    dist = {
        "left":   cx,
        "right":  1.0 - cx,
        "top":    cy,
        "bottom": 1.0 - cy,
    }
    return min(dist, key=dist.get)
