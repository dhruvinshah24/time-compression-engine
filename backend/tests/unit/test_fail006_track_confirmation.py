"""
Regression tests — Phase 6A: FAIL-006 fix.

FAIL-006: is_confirmed property used live state (ACTIVE or LOST).
          After finalize(), all LOST tracks become ENDED.
          Therefore 12 genuinely confirmed person tracks were reporting
          is_confirmed=False, starving S07 of confirmed track input.

Root cause confirmed by diagnostic:
    archive_001 60s: 13 tracks had confirmed_at_frame != None
                     Only 1 was state=ACTIVE after finalize()
                     12 were state=ENDED (previously LOST) → is_confirmed=False

Fix: is_confirmed now returns confirmed_at_frame is not None.
     A track that was ever confirmed remains confirmed regardless of
     post-finalize ENDED state.

These tests verify:
    1. is_confirmed is True when confirmed_at_frame is set
    2. is_confirmed is False only when confirmed_at_frame is None
    3. A track that goes ACTIVE → LOST → ENDED still reports is_confirmed=True
    4. A track that goes TENTATIVE → ENDED (never confirmed) reports is_confirmed=False
    5. TrackingResult.confirmed_tracks uses is_confirmed correctly
    6. MultiObjectTracker confirms tracks correctly after finalize()
"""
from __future__ import annotations

import pytest

from app.engines.perception.tracker.config import TrackerConfig
from app.engines.perception.tracker.track import Track, TrackBBox, TrackState
from app.engines.perception.tracker.tracker import MultiObjectTracker, TrackingResult
from app.model_registry.base_model import Detection, FrameDetectionResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_track(
    track_id: int = 1,
    state: TrackState = TrackState.ACTIVE,
    confirmed_at_frame: int | None = None,
) -> Track:
    bbox = TrackBBox(x1=0.1, y1=0.1, x2=0.4, y2=0.8, confidence=0.8,
                     class_id=0, class_name="person")
    return Track(
        track_id=track_id,
        class_name="person",
        class_id=0,
        state=state,
        created_frame=0,
        created_timestamp_ms=0.0,
        last_seen_frame=10,
        last_seen_timestamp_ms=400.0,
        current_bbox=bbox,
        confirmed_at_frame=confirmed_at_frame,
    )


def _det(class_name="person", confidence=0.85, x1=0.1, y1=0.1, x2=0.4, y2=0.8):
    return Detection(
        class_id=0, class_name=class_name, confidence=confidence,
        bbox_x1=x1, bbox_y1=y1, bbox_x2=x2, bbox_y2=y2,
        frame_number=0, timestamp_ms=0.0,
        model_name="stub", model_version="0.0.0",
    )


def _frame(frame_number: int, detections: list) -> FrameDetectionResult:
    return FrameDetectionResult(
        frame_number=frame_number,
        frame_path="/frames/frame_%08d.jpg" % frame_number,
        timestamp_ms=float(frame_number * 33),
        detections=detections,
        model_name="stub",
        model_version="0.0.0",
    )



# ── is_confirmed property tests ────────────────────────────────────────────────

class TestIsConfirmedProperty:
    """Direct property tests — no tracker needed."""

    def test_confirmed_at_frame_set_means_confirmed(self):
        """Track with confirmed_at_frame != None → is_confirmed=True."""
        t = _make_track(state=TrackState.ACTIVE, confirmed_at_frame=5)
        assert t.is_confirmed is True

    def test_confirmed_at_frame_none_means_not_confirmed(self):
        """Track with confirmed_at_frame=None → is_confirmed=False."""
        t = _make_track(state=TrackState.TENTATIVE, confirmed_at_frame=None)
        assert t.is_confirmed is False

    def test_ended_but_once_confirmed_is_confirmed(self):
        """A track that was confirmed and is now ENDED → still is_confirmed=True.

        This is the FAIL-006 scenario: after finalize(), tracks go LOST→ENDED.
        Their historical confirmation must be preserved.
        """
        t = _make_track(state=TrackState.ENDED, confirmed_at_frame=3)
        assert t.is_confirmed is True

    def test_ended_never_confirmed_is_not_confirmed(self):
        """A track that went TENTATIVE→ENDED without confirmation → is_confirmed=False."""
        t = _make_track(state=TrackState.ENDED, confirmed_at_frame=None)
        assert t.is_confirmed is False

    def test_lost_and_confirmed(self):
        """A LOST track that was confirmed → is_confirmed=True."""
        t = _make_track(state=TrackState.LOST, confirmed_at_frame=2)
        assert t.is_confirmed is True

    def test_lost_but_never_confirmed(self):
        """A LOST track that was never confirmed → is_confirmed=False.

        LOST can happen if a track goes TENTATIVE→LOST without meeting
        min_confirmation_frames. In that case confirmed_at_frame=None.
        """
        t = _make_track(state=TrackState.LOST, confirmed_at_frame=None)
        assert t.is_confirmed is False

    def test_active_confirmed(self):
        """ACTIVE track with confirmed_at_frame → is_confirmed=True."""
        t = _make_track(state=TrackState.ACTIVE, confirmed_at_frame=1)
        assert t.is_confirmed is True


# ── Tracker lifecycle tests ────────────────────────────────────────────────────

class TestTrackerConfirmationAfterFinalize:
    """Integration tests: MultiObjectTracker + finalize() + is_confirmed."""

    def _make_tracker(self, min_confirmation_frames: int = 2) -> MultiObjectTracker:
        config = TrackerConfig(
            iou_threshold=0.3,
            min_confirmation_frames=min_confirmation_frames,
            min_detection_confidence=0.50,  # lowered for test
            max_lost_frames=3,
        )
        return MultiObjectTracker(config=config)

    def test_confirmed_track_remains_confirmed_after_finalize(self):
        """A track matched for >= min_confirmation_frames → is_confirmed=True post-finalize.

        This is the FAIL-006 regression. Before the fix, this would return False.
        """
        tracker = self._make_tracker(min_confirmation_frames=2)
        det_a = _det(confidence=0.80, x1=0.1, y1=0.1, x2=0.4, y2=0.8)

        # Frame 0: track created (TENTATIVE, 1 match)
        tracker.update(_frame(0, [det_a]))
        # Frame 1: same detection → 2 matches → ACTIVE (confirmed)
        tracker.update(_frame(1, [det_a]))
        # Frame 2: same detection → still ACTIVE
        tracker.update(_frame(2, [det_a]))

        result = tracker.finalize()

        # At finalize, tracks that were ACTIVE may still be ACTIVE (last frame)
        # OR may have become ENDED (if they went LOST first). Either way:
        # confirmed_at_frame should be set.
        all_person = [t for t in result.all_tracks if t.class_name == "person"]
        assert len(all_person) >= 1
        confirmed = [t for t in all_person if t.is_confirmed]
        assert len(confirmed) >= 1, (
            "Expected at least 1 confirmed person track after finalize. "
            "FAIL-006 regression: is_confirmed reading post-finalize ENDED state."
        )

    def test_tentative_only_track_not_confirmed_after_finalize(self):
        """A track that only appears once (never reaches confirmation) → not confirmed."""
        tracker = self._make_tracker(min_confirmation_frames=2)
        det_a = _det(confidence=0.80)

        # Frame 0 only: 1 match → TENTATIVE, never confirmed
        tracker.update(_frame(0, [det_a]))
        # No more frames — finalize kills tentative tracks
        result = tracker.finalize()

        one_shot = [
            t for t in result.all_tracks
            if t.class_name == "person" and t.total_frames_matched == 1
        ]
        assert all(not t.is_confirmed for t in one_shot), (
            "Single-match tentative tracks must not be confirmed."
        )

    def test_confirmed_at_frame_is_set_on_confirmation(self):
        """confirmed_at_frame is set to the frame when ACTIVE was reached."""
        tracker = self._make_tracker(min_confirmation_frames=2)
        det_a = _det(confidence=0.80)

        tracker.update(_frame(10, [det_a]))  # frame 10: TENTATIVE
        tracker.update(_frame(11, [det_a]))  # frame 11: ACTIVE

        result = tracker.finalize()
        confirmed = [t for t in result.all_tracks if t.confirmed_at_frame is not None]
        assert len(confirmed) >= 1
        # confirmed_at_frame must be a valid frame number
        for t in confirmed:
            assert t.confirmed_at_frame in (10, 11), (
                "confirmed_at_frame=%s out of expected range" % t.confirmed_at_frame
            )

    def test_tracking_result_confirmed_tracks_matches_is_confirmed(self):
        """TrackingResult.confirmed_tracks uses is_confirmed — consistent post-finalize."""
        tracker = self._make_tracker(min_confirmation_frames=2)
        det_a = _det(confidence=0.80)

        for i in range(5):
            tracker.update(_frame(i, [det_a]))

        result = tracker.finalize()

        manual_confirmed = [t for t in result.all_tracks if t.is_confirmed]
        assert result.confirmed_tracks == manual_confirmed, (
            "TrackingResult.confirmed_tracks must equal all_tracks filtered by is_confirmed"
        )

    def test_multiple_confirmed_tracks_all_report_confirmed_after_finalize(self):
        """Multiple person tracks, all confirmed during video, all confirmed post-finalize.

        FAIL-006: only the still-ACTIVE track reported confirmed. This test
        verifies the full set is correctly returned.
        """
        tracker = self._make_tracker(min_confirmation_frames=2)

        # Two person detections, side by side
        det_a = _det(x1=0.1, y1=0.1, x2=0.3, y2=0.8, confidence=0.80)
        det_b = _det(x1=0.6, y1=0.1, x2=0.8, y2=0.8, confidence=0.80)

        # Both confirmed over 3 frames
        for i in range(3):
            tracker.update(_frame(i, [det_a, det_b]))

        # Person A disappears (track goes LOST → ENDED by finalize)
        for i in range(3, 6):
            tracker.update(_frame(i, [det_b]))  # only B visible

        result = tracker.finalize()

        person_tracks = [t for t in result.all_tracks if t.class_name == "person"]
        confirmed = [t for t in person_tracks if t.is_confirmed]

        # Both A and B should be confirmed (A was confirmed during frames 0-2)
        assert len(confirmed) == 2, (
            "Expected 2 confirmed person tracks (both were active during recording). "
            "Got %d confirmed. States: %s"
            % (len(confirmed), [(t.track_id, t.state, t.confirmed_at_frame) for t in person_tracks])
        )
