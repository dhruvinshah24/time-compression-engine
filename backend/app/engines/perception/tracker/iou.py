"""
IoU (Intersection over Union) computation and Hungarian matching.

These are the core mathematical primitives for multi-object tracking.

IoU measures the overlap between two bounding boxes:
    IoU = Area(Intersection) / Area(Union)
    Range: [0.0, 1.0]. 1.0 = perfect overlap, 0.0 = no overlap.

Hungarian Algorithm:
    Finds the optimal assignment between tracks and detections by
    minimizing total cost (maximizing total IoU).
    Complexity: O(n³) where n = max(tracks, detections).
    For surveillance (typically n < 50), this is negligible.

Algorithm choice rationale (Phase 4):
    IoU-based matching is the established baseline for MOT (Multi-Object
    Tracking). It is used in SORT, ByteTrack, and most production trackers
    as the primary assignment metric. We use it because:
    1. It's interpretable — threshold has clear geometric meaning.
    2. It handles overlapping objects correctly (unlike centroid distance).
    3. It's the foundation that ByteTrack and DeepSORT both build on.

    Alternative: Mahalanobis distance (used in DeepSORT) — requires a
    Kalman filter state estimate. Added in Phase 9 if tracking accuracy
    evaluation shows IoU matching is insufficient.

    Alternative: Appearance embeddings (ReID) — requires a CNN feature
    extractor. Expensive. Planned as Phase 9 upgrade if object re-ID
    across occlusions becomes a bottleneck.
"""

from __future__ import annotations

import numpy as np


def compute_iou(box_a: tuple, box_b: tuple) -> float:
    """
    Compute IoU between two bounding boxes.

    Args:
        box_a: (x1, y1, x2, y2) normalized coordinates
        box_b: (x1, y1, x2, y2) normalized coordinates

    Returns:
        IoU float in [0.0, 1.0]
    """
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    # Intersection
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    intersection = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return float(intersection / union)


def compute_iou_matrix(
    tracks_boxes: list[tuple],
    detection_boxes: list[tuple],
) -> np.ndarray:
    """
    Compute the full IoU matrix between tracks and detections.

    Args:
        tracks_boxes:     List of (x1, y1, x2, y2) tuples for each track.
        detection_boxes:  List of (x1, y1, x2, y2) tuples for each detection.

    Returns:
        numpy array of shape (len(tracks), len(detections))
        Each element iou_matrix[i, j] = IoU(track_i, detection_j)
    """
    n_tracks = len(tracks_boxes)
    n_detections = len(detection_boxes)

    if n_tracks == 0 or n_detections == 0:
        return np.zeros((n_tracks, n_detections), dtype=np.float32)

    iou_matrix = np.zeros((n_tracks, n_detections), dtype=np.float32)
    for i, track_box in enumerate(tracks_boxes):
        for j, det_box in enumerate(detection_boxes):
            iou_matrix[i, j] = compute_iou(track_box, det_box)

    return iou_matrix


def hungarian_match(
    iou_matrix: np.ndarray,
    iou_threshold: float = 0.3,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """
    Run the Hungarian algorithm on an IoU matrix to find optimal assignments.

    Uses scipy.optimize.linear_sum_assignment (Jonker-Volgenant algorithm,
    O(n³) worst case) on the cost matrix (1 - IoU).

    Args:
        iou_matrix:    Shape (n_tracks, n_detections). IoU scores.
        iou_threshold: Minimum IoU for a valid match. Pairs below this
                       are discarded (treated as unmatched).

    Returns:
        matched:         list of (track_idx, detection_idx) pairs
        unmatched_tracks:     track indices with no valid match
        unmatched_detections: detection indices with no valid match
    """
    if iou_matrix.size == 0:
        n_tracks, n_detections = iou_matrix.shape
        return [], list(range(n_tracks)), list(range(n_detections))

    from scipy.optimize import linear_sum_assignment

    # Cost = 1 - IoU (Hungarian minimizes cost)
    cost_matrix = 1.0 - iou_matrix
    row_indices, col_indices = linear_sum_assignment(cost_matrix)

    matched: list[tuple[int, int]] = []
    unmatched_tracks: list[int] = []
    unmatched_detections: list[int] = []

    # Filter out pairs below IoU threshold
    matched_track_set: set[int] = set()
    matched_detection_set: set[int] = set()

    for track_idx, det_idx in zip(row_indices, col_indices):
        if iou_matrix[track_idx, det_idx] >= iou_threshold:
            matched.append((int(track_idx), int(det_idx)))
            matched_track_set.add(int(track_idx))
            matched_detection_set.add(int(det_idx))

    n_tracks, n_detections = iou_matrix.shape
    unmatched_tracks = [i for i in range(n_tracks) if i not in matched_track_set]
    unmatched_detections = [j for j in range(n_detections) if j not in matched_detection_set]

    return matched, unmatched_tracks, unmatched_detections
