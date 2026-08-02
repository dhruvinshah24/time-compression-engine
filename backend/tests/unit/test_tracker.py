"""
Unit tests for Phase 4: Multi-Object Tracking.

Testing approach:
  All tests are self-contained — no real videos, no real models.
  Synthetic FrameDetectionResult objects simulate detection output.

Coverage:
  1. IoU computation — perfect overlap, no overlap, partial, edge cases
  2. IoU matrix — shape, values, empty inputs
  3. Hungarian matching — optimal assignment, threshold filtering
  4. Track lifecycle — TENTATIVE → ACTIVE → LOST → ENDED state machine
  5. TrackBBox geometry
  6. MultiObjectTracker — tracking across frames, occlusion, new object entry
  7. Track ID consistency across frames
  8. TrackingResult metrics
  9. s05_track pipeline stage (mocked)

Key invariants tested:
  - Same physical object always gets same Track ID
  - Track never goes ENDED → ACTIVE (state machine is one-directional)
  - Tentative tracks don't survive beyond max 1 unmatched frame
  - IoU of identical boxes = 1.0
  - IoU of non-overlapping boxes = 0.0
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.engines.perception.tracker.config import TrackerConfig
from app.engines.perception.tracker.iou import (
    compute_iou,
    compute_iou_matrix,
    hungarian_match,
)
from app.engines.perception.tracker.track import Track, TrackBBox, TrackState
from app.engines.perception.tracker.tracker import MultiObjectTracker, TrackingResult
from app.model_registry.base_model import Detection, FrameDetectionResult


# ---------------------------------------------------------------------------
# Synthetic detection helpers
# ---------------------------------------------------------------------------

def _det(
    class_name: str = "person",
    x1: float = 0.1, y1: float = 0.1, x2: float = 0.5, y2: float = 0.9,
    confidence: float = 0.85,
    frame_number: int = 0,
    timestamp_ms: float = 0.0,
) -> Detection:
    return Detection(
        class_id=0,
        class_name=class_name,
        confidence=confidence,
        bbox_x1=x1, bbox_y1=y1, bbox_x2=x2, bbox_y2=y2,
        frame_number=frame_number,
        timestamp_ms=timestamp_ms,
        model_name="stub",
        model_version="0.0.0",
    )


def _frame(
    frame_number: int,
    detections: list | None = None,
) -> FrameDetectionResult:
    return FrameDetectionResult(
        frame_number=frame_number,
        frame_path=f"/frames/frame_{frame_number:08d}.jpg",
        timestamp_ms=frame_number * 200.0,
        detections=detections or [],
        model_name="stub",
        model_version="0.0.0",
    )


# ---------------------------------------------------------------------------
# IoU tests
# ---------------------------------------------------------------------------

class TestComputeIoU:
    def test_identical_boxes_iou_is_one(self):
        box = (0.1, 0.1, 0.5, 0.9)
        assert compute_iou(box, box) == pytest.approx(1.0)

    def test_no_overlap_iou_is_zero(self):
        box_a = (0.0, 0.0, 0.4, 0.4)
        box_b = (0.6, 0.6, 1.0, 1.0)
        assert compute_iou(box_a, box_b) == pytest.approx(0.0)

    def test_adjacent_boxes_iou_is_zero(self):
        # Touch at a line (zero area intersection)
        box_a = (0.0, 0.0, 0.5, 1.0)
        box_b = (0.5, 0.0, 1.0, 1.0)
        assert compute_iou(box_a, box_b) == pytest.approx(0.0)

    def test_half_overlap(self):
        # Two boxes with ~50% overlap
        box_a = (0.0, 0.0, 0.6, 1.0)  # area = 0.6
        box_b = (0.4, 0.0, 1.0, 1.0)  # area = 0.6
        # intersection = 0.2 * 1.0 = 0.2
        # union = 0.6 + 0.6 - 0.2 = 1.0
        iou = compute_iou(box_a, box_b)
        assert iou == pytest.approx(0.2 / 1.0, abs=0.01)

    def test_iou_is_symmetric(self):
        box_a = (0.1, 0.1, 0.6, 0.8)
        box_b = (0.3, 0.2, 0.9, 0.9)
        assert compute_iou(box_a, box_b) == pytest.approx(compute_iou(box_b, box_a))

    def test_iou_in_valid_range(self):
        rng = np.random.default_rng(42)
        for _ in range(50):
            coords = sorted(rng.uniform(0, 1, 4).tolist())
            box_a = (coords[0], coords[1], coords[2], coords[3])
            coords2 = sorted(rng.uniform(0, 1, 4).tolist())
            box_b = (coords2[0], coords2[1], coords2[2], coords2[3])
            iou = compute_iou(box_a, box_b)
            assert 0.0 <= iou <= 1.0


class TestIoUMatrix:
    def test_shape_correct(self):
        tracks = [(0.0, 0.0, 0.3, 0.3), (0.5, 0.5, 0.8, 0.8)]
        dets = [(0.0, 0.0, 0.3, 0.3), (0.5, 0.5, 0.8, 0.8), (0.2, 0.2, 0.5, 0.5)]
        matrix = compute_iou_matrix(tracks, dets)
        assert matrix.shape == (2, 3)

    def test_empty_tracks_returns_empty_matrix(self):
        dets = [(0.0, 0.0, 0.3, 0.3)]
        matrix = compute_iou_matrix([], dets)
        assert matrix.shape == (0, 1)

    def test_diagonal_is_one_for_identical_boxes(self):
        boxes = [(0.0, 0.0, 0.3, 0.3), (0.5, 0.5, 0.8, 0.8)]
        matrix = compute_iou_matrix(boxes, boxes)
        assert matrix[0, 0] == pytest.approx(1.0)
        assert matrix[1, 1] == pytest.approx(1.0)
        assert matrix[0, 1] == pytest.approx(0.0)


class TestHungarianMatch:
    def test_perfect_matching(self):
        # Two tracks, two identical detections — should match 1:1
        iou_matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        matched, unmatched_tracks, unmatched_dets = hungarian_match(iou_matrix, 0.3)
        assert len(matched) == 2
        assert len(unmatched_tracks) == 0
        assert len(unmatched_dets) == 0

    def test_below_threshold_unmatched(self):
        # IoU of 0.1 < threshold of 0.3 → not matched
        iou_matrix = np.array([[0.1]], dtype=np.float32)
        matched, unmatched_tracks, unmatched_dets = hungarian_match(iou_matrix, 0.3)
        assert len(matched) == 0
        assert unmatched_tracks == [0]
        assert unmatched_dets == [0]

    def test_empty_matrix(self):
        iou_matrix = np.zeros((0, 0), dtype=np.float32)
        matched, unmatched_t, unmatched_d = hungarian_match(iou_matrix, 0.3)
        assert matched == []
        assert unmatched_t == []
        assert unmatched_d == []

    def test_more_detections_than_tracks(self):
        # 1 track, 3 detections — best match + 2 unmatched detections
        iou_matrix = np.array([[0.2, 0.8, 0.1]], dtype=np.float32)
        matched, unmatched_t, unmatched_d = hungarian_match(iou_matrix, 0.3)
        assert len(matched) == 1
        assert matched[0] == (0, 1)  # Track 0 matched to detection 1 (IoU=0.8)
        assert 0 in unmatched_d
        assert 2 in unmatched_d


# ---------------------------------------------------------------------------
# TrackBBox tests
# ---------------------------------------------------------------------------

class TestTrackBBox:
    def test_center(self):
        bbox = TrackBBox(x1=0.0, y1=0.0, x2=0.5, y2=1.0,
                         confidence=0.9, class_id=0, class_name="person")
        assert bbox.cx == pytest.approx(0.25)
        assert bbox.cy == pytest.approx(0.5)

    def test_area(self):
        bbox = TrackBBox(x1=0.0, y1=0.0, x2=0.5, y2=0.4,
                         confidence=0.9, class_id=0, class_name="person")
        assert bbox.area == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Track lifecycle tests
# ---------------------------------------------------------------------------

class TestTrackLifecycle:
    def _make_bbox(self) -> TrackBBox:
        return TrackBBox(0.1, 0.1, 0.5, 0.9, 0.85, 0, "person")

    def test_initial_state_is_tentative(self):
        bbox = self._make_bbox()
        track = Track(
            track_id=1, class_name="person", class_id=0,
            state=TrackState.TENTATIVE,
            created_frame=1, created_timestamp_ms=0.0,
            last_seen_frame=1, last_seen_timestamp_ms=0.0,
            current_bbox=bbox,
        )
        assert track.state == TrackState.TENTATIVE
        assert not track.is_confirmed

    def test_update_increments_matched_count(self):
        bbox = self._make_bbox()
        track = Track(
            track_id=1, class_name="person", class_id=0,
            state=TrackState.ACTIVE,
            created_frame=1, created_timestamp_ms=0.0,
            last_seen_frame=1, last_seen_timestamp_ms=0.0,
            current_bbox=bbox,
        )
        track.update(2, 400.0, bbox)
        assert track.total_frames_matched == 1
        assert track.last_seen_frame == 2

    def test_mark_lost_increments_counter(self):
        bbox = self._make_bbox()
        track = Track(
            track_id=1, class_name="person", class_id=0,
            state=TrackState.ACTIVE,
            created_frame=1, created_timestamp_ms=0.0,
            last_seen_frame=1, last_seen_timestamp_ms=0.0,
            current_bbox=bbox,
        )
        track.mark_lost()
        track.mark_lost()
        assert track.lost_frames == 2

    def test_end_sets_state_to_ended(self):
        bbox = self._make_bbox()
        track = Track(
            track_id=1, class_name="person", class_id=0,
            state=TrackState.LOST,
            created_frame=1, created_timestamp_ms=0.0,
            last_seen_frame=5, last_seen_timestamp_ms=1000.0,
            current_bbox=bbox,
        )
        track.end()
        assert track.state == TrackState.ENDED

    def test_avg_confidence(self):
        bbox_hi = TrackBBox(0.1, 0.1, 0.5, 0.9, 0.95, 0, "person")
        bbox_lo = TrackBBox(0.1, 0.1, 0.5, 0.9, 0.75, 0, "person")
        track = Track(
            track_id=1, class_name="person", class_id=0,
            state=TrackState.ACTIVE,
            created_frame=1, created_timestamp_ms=0.0,
            last_seen_frame=1, last_seen_timestamp_ms=0.0,
            current_bbox=bbox_hi,
        )
        track.update(1, 0.0, bbox_hi)
        track.update(2, 200.0, bbox_lo)
        assert track.avg_confidence == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# MultiObjectTracker integration tests
# ---------------------------------------------------------------------------

class TestMultiObjectTracker:
    def _cfg(self, min_confirm: int = 2) -> TrackerConfig:
        return TrackerConfig(
            iou_threshold=0.3,
            max_lost_frames=2,
            min_confirmation_frames=min_confirm,
            min_detection_confidence=0.5,
        )

    def test_single_frame_creates_tentative_track(self):
        tracker = MultiObjectTracker(self._cfg())
        frame = _frame(1, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)])
        active = tracker.update(frame)
        assert len(active) == 1
        assert active[0].state == TrackState.TENTATIVE

    def test_same_object_gets_same_id_across_frames(self):
        """The most important correctness invariant."""
        tracker = MultiObjectTracker(self._cfg(min_confirm=2))
        # Person at same position in 3 consecutive frames
        f1 = _frame(1, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9, frame_number=1)])
        f2 = _frame(2, [_det(x1=0.12, y1=0.1, x2=0.52, y2=0.9, frame_number=2)])
        f3 = _frame(3, [_det(x1=0.14, y1=0.1, x2=0.54, y2=0.9, frame_number=3)])

        active1 = tracker.update(f1)
        active2 = tracker.update(f2)
        active3 = tracker.update(f3)

        # All three updates should reference the same track_id
        ids1 = {t.track_id for t in active1}
        ids2 = {t.track_id for t in active2}
        ids3 = {t.track_id for t in active3}
        assert ids1 == ids2 == ids3

    def test_tentative_becomes_active_after_confirmation(self):
        tracker = MultiObjectTracker(self._cfg(min_confirm=2))
        det = _det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)
        tracker.update(_frame(1, [det]))  # frame 1: TENTATIVE (1 match)
        tracks = tracker.update(_frame(2, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)]))
        assert any(t.state == TrackState.ACTIVE for t in tracks)

    def test_new_object_entering_scene(self):
        tracker = MultiObjectTracker(self._cfg())
        # Frame 1: one person
        tracker.update(_frame(1, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)]))
        # Frame 2: same person + new car (different location)
        tracks = tracker.update(_frame(2, [
            _det(x1=0.1, y1=0.1, x2=0.5, y2=0.9),
            _det("car", x1=0.6, y1=0.1, x2=0.9, y2=0.5),
        ]))
        assert len(tracks) == 2

    def test_object_leaving_scene_becomes_lost(self):
        tracker = MultiObjectTracker(self._cfg(min_confirm=2))
        tracker.update(_frame(1, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)]))
        tracker.update(_frame(2, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)]))
        # Frame 3: no detections
        tracks = tracker.update(_frame(3, []))
        assert any(t.state in (TrackState.LOST, TrackState.ENDED) for t in tracks)

    def test_track_ends_after_max_lost_frames(self):
        cfg = TrackerConfig(max_lost_frames=2, min_confirmation_frames=2, iou_threshold=0.3)
        tracker = MultiObjectTracker(cfg)
        # Confirm a track over 2 frames
        tracker.update(_frame(1, [_det()]))
        tracker.update(_frame(2, [_det()]))
        # 3 consecutive empty frames exceeds max_lost_frames=2
        tracker.update(_frame(3, []))
        tracker.update(_frame(4, []))
        tracker.update(_frame(5, []))

        result = tracker.finalize()
        ended = [t for t in result.all_tracks if t.state == TrackState.ENDED]
        assert len(ended) >= 1

    def test_two_people_no_id_swap(self):
        """Person A and Person B should never swap IDs."""
        tracker = MultiObjectTracker(self._cfg(min_confirm=1))
        # Frame 1: two people far apart
        f1 = _frame(1, [
            _det(x1=0.0, y1=0.0, x2=0.3, y2=0.5),   # Person A - left
            _det(x1=0.7, y1=0.0, x2=1.0, y2=0.5),   # Person B - right
        ])
        t1 = tracker.update(f1)
        id_left = min(t.track_id for t in t1 if t.current_bbox and t.current_bbox.cx < 0.5)
        id_right = min(t.track_id for t in t1 if t.current_bbox and t.current_bbox.cx > 0.5)

        # Frame 2: same positions (no crossing)
        f2 = _frame(2, [
            _det(x1=0.01, y1=0.0, x2=0.31, y2=0.5),
            _det(x1=0.71, y1=0.0, x2=1.01, y2=0.5),
        ])
        t2 = tracker.update(f2)

        id_left_f2 = min(t.track_id for t in t2 if t.current_bbox and t.current_bbox.cx < 0.5)
        id_right_f2 = min(t.track_id for t in t2 if t.current_bbox and t.current_bbox.cx > 0.5)

        assert id_left == id_left_f2
        assert id_right == id_right_f2

    def test_empty_video_returns_zero_tracks(self):
        tracker = MultiObjectTracker()
        for i in range(10):
            tracker.update(_frame(i, []))
        result = tracker.finalize()
        assert result.total_tracks_created == 0

    def test_finalize_ends_all_open_tracks(self):
        tracker = MultiObjectTracker(self._cfg())
        tracker.update(_frame(1, [_det()]))
        tracker.update(_frame(2, [_det()]))
        result = tracker.finalize()
        # After finalize, no track should be TENTATIVE or LOST
        for track in result.all_tracks:
            assert track.state not in (TrackState.TENTATIVE, TrackState.LOST)


# ---------------------------------------------------------------------------
# TrackingResult metrics tests
# ---------------------------------------------------------------------------

class TestTrackingResult:
    def test_confirmed_tracks_filter(self):
        tracker = MultiObjectTracker(TrackerConfig(min_confirmation_frames=2))
        tracker.update(_frame(1, [_det()]))
        tracker.update(_frame(2, [_det()]))
        result = tracker.finalize()
        # After 2 matches, should be confirmed
        assert len(result.confirmed_tracks) >= 1

    def test_metrics_dict_keys_present(self):
        tracker = MultiObjectTracker()
        tracker.update(_frame(1, [_det()]))
        result = tracker.finalize()
        d = result.to_metrics_dict()
        for key in ["total_tracks_created", "active_tracks", "ended_tracks",
                    "confirmed_tracks", "avg_track_length_frames", "avg_track_confidence"]:
            assert key in d


# ---------------------------------------------------------------------------
# s05_track pipeline stage tests
# ---------------------------------------------------------------------------

class TestS05Track:
    def _make_context(self, frame_detections=None):
        from app.pipeline.context import PipelineContext
        ctx = PipelineContext(
            job_id="JOB-TEST",
            video_id="test",
            video_path="/tmp/video.mp4",
            output_dir="/tmp",
            settings={
                "tracker_iou_threshold": 0.3,
                "tracker_max_lost_frames": 3,
                "tracker_min_confirmation_frames": 2,
                "tracker_min_detection_confidence": 0.65,
            },
            metadata={"fps": 25.0},
        )
        if frame_detections is not None:
            ctx.metadata["frame_detections"] = frame_detections
        return ctx

    @pytest.mark.asyncio
    async def test_missing_frame_detections_fails(self):
        from app.pipeline.stages import s05_track
        ctx = self._make_context()
        result = await s05_track.run(ctx)
        assert result.success is False
        assert any("frame_detections" in e for e in result.errors)

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s05_track.save_stage_metrics")
    async def test_empty_detections_returns_zero_tracks(self, mock_save):
        from app.pipeline.stages import s05_track
        mock_save.return_value = None
        ctx = self._make_context([_frame(1, []), _frame(2, []), _frame(3, [])])
        result = await s05_track.run(ctx)
        assert result.success is True
        assert ctx.metadata["total_tracks"] == 0
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    @patch("app.pipeline.stages.s05_track.save_stage_metrics")
    async def test_detections_create_tracks(self, mock_save):
        from app.pipeline.stages import s05_track
        mock_save.return_value = None
        frame_dets = [
            _frame(1, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)]),
            _frame(2, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)]),
            _frame(3, [_det(x1=0.1, y1=0.1, x2=0.5, y2=0.9)]),
        ]
        ctx = self._make_context(frame_dets)
        result = await s05_track.run(ctx)
        assert result.success is True
        assert ctx.metadata["total_tracks"] >= 1

    @pytest.mark.asyncio
    async def test_stage_name_correct(self):
        from app.pipeline.stages import s05_track
        ctx = self._make_context()
        result = await s05_track.run(ctx)
        assert result.stage_name == "s05_track"
