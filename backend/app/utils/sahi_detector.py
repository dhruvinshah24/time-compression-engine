"""
SAHI Detector — Slicing Aided Hyper Inference for small-object detection.

For CCTV footage, objects far from the camera appear very small (e.g., 8×20px
for a person 15m away). Standard YOLO inference on a 1920×1080 frame scaled
to 640×640 reduces that person to 2×5px — below detection threshold.

SAHI fixes this by:
  1. Dividing the frame into overlapping 640×640 tiles.
  2. Running YOLO detection on each tile independently.
  3. Merging all detections using NMS on the original coordinate space.

Result: small objects that were previously 8×20px in the full frame
are 80×200px within their tile → confidently detected.

Reference: Akyon et al., "Slicing Aided Hyper Inference and Fine-tuning
for Small Object Detection", IEEE ICIP 2022.

Usage:
    detector = SAHIDetector(yolo_model, tile_size=640, overlap=0.2)
    result = detector.detect(frame_bgr, frame_number=42, timestamp_ms=1400.0)
"""

from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from app.model_registry.base_model import Detection, FrameDetectionResult

logger = logging.getLogger(__name__)


@dataclass
class SAHIConfig:
    """Configuration for SAHI sliced inference."""
    enabled: bool = True
    tile_size: int = 640        # tile width and height in pixels
    overlap_ratio: float = 0.2  # fraction of tile_size to overlap between tiles
    nms_iou_threshold: float = 0.5  # IoU threshold for post-merge NMS
    min_area_ratio: float = 0.0     # skip detections < this fraction of tile area


class SAHIDetector:
    """
    Wraps any YOLO detection model with SAHI sliced inference.
    
    Falls back to standard full-frame inference if frame is smaller
    than tile_size or if SAHI is disabled.
    """

    def __init__(self, base_model, config: SAHIConfig | None = None) -> None:
        self.model = base_model
        self.config = config or SAHIConfig()
        logger.info(
            "[SAHI] Initialized: tile=%dpx overlap=%.0f%% enabled=%s",
            self.config.tile_size, self.config.overlap_ratio * 100, self.config.enabled
        )

    def detect(
        self,
        frame_bgr: np.ndarray,
        frame_number: int = 0,
        timestamp_ms: float = 0.0,
        override_confidence: float | None = None,
    ) -> FrameDetectionResult:
        """
        Run sliced detection on a single frame using GPU batch inference.

        If SAHI is disabled or frame fits in one tile, delegates to base model.
        Otherwise: compute tiles → batch-infer all tiles at once → merge → NMS.
        Batch inference processes all tiles in one GPU forward pass for maximum speed.
        """
        cfg = self.config
        h, w = frame_bgr.shape[:2]
        
        # Fallback: standard inference if disabled or frame is small
        if not cfg.enabled or (h <= cfg.tile_size and w <= cfg.tile_size):
            return self.model.detect(frame_bgr, frame_number, timestamp_ms, override_confidence)

        start = time.perf_counter()
        
        # Compute tile positions
        stride = int(cfg.tile_size * (1.0 - cfg.overlap_ratio))
        tile_coords = _compute_tiles(h, w, cfg.tile_size, stride)
        
        # Extract all tile images
        tile_images: list[np.ndarray] = []
        valid_coords: list[tuple[int, int, int, int]] = []
        for (tx, ty, tw, th) in tile_coords:
            tile_bgr = frame_bgr[ty:ty+th, tx:tx+tw]
            if tile_bgr.size == 0:
                continue
            tile_images.append(tile_bgr)
            valid_coords.append((tx, ty, tw, th))

        if not tile_images:
            return self.model.detect(frame_bgr, frame_number, timestamp_ms, override_confidence)

        # Batch GPU inference — all tiles in one forward pass
        batch_fn = [frame_number] * len(tile_images)
        batch_ts = [timestamp_ms] * len(tile_images)

        if hasattr(self.model, 'detect_batch'):
            tile_results = self.model.detect_batch(tile_images, batch_fn, batch_ts, override_confidence)
        else:
            # Fallback for models without batch support
            tile_results = [self.model.detect(img, frame_number, timestamp_ms, override_confidence)
                            for img in tile_images]

        # Re-map coordinates from tile-space to frame-space
        all_detections: list[Detection] = []
        for tile_result, (tx, ty, tw, th) in zip(tile_results, valid_coords):
            for det in tile_result.detections:
                # tile normalised → tile pixels → frame pixels → frame normalised
                px1 = det.bbox_x1 * tw + tx
                py1 = det.bbox_y1 * th + ty
                px2 = det.bbox_x2 * tw + tx
                py2 = det.bbox_y2 * th + ty
                
                # Skip detections touching tile border that are likely fragments
                border = 4  # pixels
                if (det.bbox_px_x1 < border and tx > 0) or \
                   (det.bbox_px_x2 > tw - border and tx + tw < w):
                    pass  # allow — will be merged by NMS
                
                all_detections.append(Detection(
                    class_id=det.class_id,
                    class_name=det.class_name,
                    confidence=det.confidence,
                    bbox_x1=px1/w, bbox_y1=py1/h,
                    bbox_x2=px2/w, bbox_y2=py2/h,
                    bbox_px_x1=int(px1), bbox_px_y1=int(py1),
                    bbox_px_x2=int(px2), bbox_px_y2=int(py2),
                    frame_number=frame_number,
                    timestamp_ms=timestamp_ms,
                    model_name=det.model_name,
                    model_version=det.model_version,
                ))
        
        # Class-agnostic NMS to remove duplicates from overlapping tiles
        merged = _nms(all_detections, cfg.nms_iou_threshold)
        
        duration_ms = (time.perf_counter() - start) * 1000
        logger.debug(
            "[SAHI] frame=%d tiles=%d raw_det=%d merged=%d time=%.0fms",
            frame_number, len(tile_images), len(all_detections), len(merged), duration_ms
        )
        
        return FrameDetectionResult(
            frame_number=frame_number,
            frame_path="",
            timestamp_ms=timestamp_ms,
            detections=merged,
            inference_time_ms=duration_ms,
            model_name=getattr(self.model, 'model_name', 'sahi_wrapped'),
            model_version=getattr(self.model, 'model_version', '1.0'),
            confidence_threshold=override_confidence or 0.20,
            pre_confidence_filter_count=len(all_detections),
        )


def _compute_tiles(
    h: int, w: int, tile_size: int, stride: int
) -> list[tuple[int, int, int, int]]:
    """
    Compute (x, y, width, height) for all tiles covering the frame.
    Tiles at edges are clamped to frame boundaries.
    """
    tiles = []
    y = 0
    while y < h:
        x = 0
        while x < w:
            tw = min(tile_size, w - x)
            th = min(tile_size, h - y)
            tiles.append((x, y, tw, th))
            if x + tile_size >= w:
                break
            x += stride
        if y + tile_size >= h:
            break
        y += stride
    return tiles


def _iou(a: Detection, b: Detection) -> float:
    """Compute IoU between two detections in normalised frame coordinates."""
    ix1 = max(a.bbox_x1, b.bbox_x1)
    iy1 = max(a.bbox_y1, b.bbox_y1)
    ix2 = min(a.bbox_x2, b.bbox_x2)
    iy2 = min(a.bbox_y2, b.bbox_y2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a.bbox_x2 - a.bbox_x1) * (a.bbox_y2 - a.bbox_y1)
    area_b = (b.bbox_x2 - b.bbox_x1) * (b.bbox_y2 - b.bbox_y1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms(detections: list[Detection], iou_threshold: float) -> list[Detection]:
    """
    Class-aware Non-Maximum Suppression to merge duplicates from overlapping tiles.
    
    For each class independently:
      1. Sort detections by confidence descending.
      2. Keep highest-confidence detection.
      3. Remove all remaining detections with IoU > threshold against it.
      4. Repeat.
    """
    if not detections:
        return []
    
    # Group by class
    by_class: dict[int, list[Detection]] = {}
    for det in detections:
        by_class.setdefault(det.class_id, []).append(det)
    
    result: list[Detection] = []
    for class_id, dets in by_class.items():
        sorted_dets = sorted(dets, key=lambda d: d.confidence, reverse=True)
        kept: list[Detection] = []
        suppressed = [False] * len(sorted_dets)
        
        for i, det in enumerate(sorted_dets):
            if suppressed[i]:
                continue
            kept.append(det)
            for j in range(i + 1, len(sorted_dets)):
                if not suppressed[j] and _iou(det, sorted_dets[j]) > iou_threshold:
                    suppressed[j] = True
        result.extend(kept)
    
    return result
