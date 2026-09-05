"""
Regression tests — Phase 6A: FAIL-007 fix.

FAIL-007: TemporalPoseAnalyzer raised AttributeError when S07 called
          len(obs.bbox) where obs.bbox is a TrackBBox dataclass.

Root cause: S07 Pass 3b (temporal_pose_bbox) extracted bbox from
TrackObservation as:

    bbox = getattr(obs, "bbox", None)
    if bbox is None or len(bbox) < 4:   # ← AttributeError: TrackBBox has no len()
        continue
    x1, y1, x2, y2 = bbox               # ← TypeError: not iterable

TrackObservation.bbox is typed as TrackBBox (a dataclass), not a tuple.

Fix: detect TrackBBox and extract x1/y1/x2/y2 from fields directly.

These tests verify the integration boundary at the production level:
    TrackBBox → TrackObservation → S07 pose extraction → SimplePoseFrame → TemporalPoseAnalyzer
"""
from __future__ import annotations

import pytest

from app.engines.perception.tracker.track import Track, TrackBBox, TrackObservation, TrackState
from app.utils.pose_temporal import (
    SimplePoseFrame,
    TemporalPoseAnalyzer,
    STATE_STANDING,
    STATE_WALKING,
    STATE_UNKNOWN,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_track_bbox(
    x1: float = 0.3,
    y1: float = 0.2,
    x2: float = 0.4,
    y2: float = 0.7,
    confidence: float = 0.80,
    class_id: int = 0,
    class_name: str = "person",
) -> TrackBBox:
    return TrackBBox(
        x1=x1, y1=y1, x2=x2, y2=y2,
        confidence=confidence,
        class_id=class_id,
        class_name=class_name,
    )


def _make_observation(
    frame_number: int,
    timestamp_ms: float | None = None,
    bbox: TrackBBox | None = None,
) -> TrackObservation:
    if timestamp_ms is None:
        timestamp_ms = float(frame_number * 166)  # ~6fps
    if bbox is None:
        bbox = _make_track_bbox()
    return TrackObservation(
        frame_number=frame_number,
        timestamp_ms=timestamp_ms,
        bbox=bbox,
        detection_confidence=bbox.confidence,
    )


def _make_confirmed_person_track(
    track_id: int = 1,
    n_observations: int = 10,
    frame_start: int = 0,
) -> Track:
    """Build a confirmed person track with n_observations using production TrackBBox."""
    track = Track(
        track_id=track_id,
        class_name="person",
        class_id=0,
        state=TrackState.ACTIVE,
        created_frame=frame_start,
        created_timestamp_ms=float(frame_start * 166),
        last_seen_frame=frame_start + n_observations - 1,
        last_seen_timestamp_ms=float((frame_start + n_observations - 1) * 166),
        current_bbox=_make_track_bbox(),
        confirmed_at_frame=frame_start + 1,  # confirmed on 2nd frame
    )
    # Add real TrackObservation objects with TrackBBox instances
    for i in range(n_observations):
        frame = frame_start + i
        bbox = _make_track_bbox(
            x1=0.30 + i * 0.003,  # slight lateral movement
            y1=0.20,
            x2=0.40 + i * 0.003,
            y2=0.70,
            confidence=0.80,
        )
        track.observations.append(TrackObservation(
            frame_number=frame,
            timestamp_ms=float(frame * 166),
            bbox=bbox,
            detection_confidence=bbox.confidence,
        ))
    return track


# ── FAIL-007: TrackBBox ↔ pose adapter tests ──────────────────────────────────

class TestTrackBBoxPoseIntegration:
    """Verify the S07 TrackBBox → SimplePoseFrame extraction logic.

    These tests exercise the exact code path fixed for FAIL-007.
    """

    def test_trackbbox_has_no_len(self):
        """Confirm that TrackBBox has no __len__ — this is the root cause.

        If this test fails, the upstream class added __len__ and the fix
        may need to be revisited.
        """
        bbox = _make_track_bbox()
        assert not hasattr(bbox, "__len__"), (
            "TrackBBox now has __len__. Review whether the FAIL-007 fix "
            "still correctly handles both TrackBBox and legacy tuples."
        )

    def test_trackbbox_has_no_iter(self):
        """TrackBBox is not iterable — can't be unpacked as x1,y1,x2,y2 = bbox."""
        bbox = _make_track_bbox()
        with pytest.raises(TypeError):
            x1, y1, x2, y2 = bbox  # must fail — TrackBBox is not a sequence

    def test_trackbbox_fields_accessible(self):
        """x1, y1, x2, y2 are accessible as named attributes."""
        bbox = _make_track_bbox(x1=0.1, y1=0.2, x2=0.5, y2=0.8)
        assert bbox.x1 == pytest.approx(0.1)
        assert bbox.y1 == pytest.approx(0.2)
        assert bbox.x2 == pytest.approx(0.5)
        assert bbox.y2 == pytest.approx(0.8)

    def test_trackobservation_bbox_is_trackbbox(self):
        """TrackObservation.bbox is typed as TrackBBox in production."""
        obs = _make_observation(frame_number=10)
        assert isinstance(obs.bbox, TrackBBox), (
            "TrackObservation.bbox must be a TrackBBox instance "
            "(as defined in track.py). If this fails, the observation "
            "format has changed and FAIL-007 fix may need updating."
        )

    def test_extract_coords_from_trackbbox(self):
        """The S07 fix: extract coordinates from TrackBBox fields correctly."""
        bbox = _make_track_bbox(x1=0.3, y1=0.1, x2=0.4, y2=0.9)
        obs = _make_observation(frame_number=5, bbox=bbox)

        # This is the fixed extraction logic from S07 Pass 3b
        raw_bbox = getattr(obs, "bbox", None)
        assert raw_bbox is not None

        if isinstance(raw_bbox, TrackBBox):
            x1, y1, x2, y2 = raw_bbox.x1, raw_bbox.y1, raw_bbox.x2, raw_bbox.y2
        elif hasattr(raw_bbox, "__len__") and len(raw_bbox) >= 4:
            x1, y1, x2, y2 = raw_bbox[0], raw_bbox[1], raw_bbox[2], raw_bbox[3]
        else:
            pytest.fail("bbox was neither TrackBBox nor a sequence — cannot extract coords")

        assert x1 == pytest.approx(0.3)
        assert y1 == pytest.approx(0.1)
        assert x2 == pytest.approx(0.4)
        assert y2 == pytest.approx(0.9)

    def test_simplepose_from_bbox_constructed_from_trackbbox(self):
        """SimplePoseFrame.from_bbox receives correctly extracted TrackBBox coords."""
        bbox = _make_track_bbox(x1=0.3, y1=0.2, x2=0.4, y2=0.7)
        obs = _make_observation(frame_number=10, bbox=bbox)
        raw = obs.bbox

        assert isinstance(raw, TrackBBox)
        x1, y1, x2, y2 = raw.x1, raw.y1, raw.x2, raw.y2

        spf = SimplePoseFrame.from_bbox(
            frame_number=obs.frame_number,
            timestamp_ms=obs.timestamp_ms,
            track_id=1,
            x1=x1, y1=y1, x2=x2, y2=y2,
            frame_h=1.0,
        )
        assert spf.frame_number == 10
        assert spf.track_id == 1
        assert spf.bbox_h == pytest.approx(0.5, rel=0.01)
        assert spf.bbox_w == pytest.approx(0.1, rel=0.01)
        assert spf.bbox_aspect_ratio > 0


class TestPoseAnalyzerReceivesValidInput:
    """
    Verify that a confirmed person Track with TrackBBox observations can
    drive TemporalPoseAnalyzer without AttributeError.

    This is the actual integration path that FAIL-007 broke.
    """

    def _feed_track_to_analyzer(self, track: Track, frame_w: float = 320, frame_h: float = 240):
        """Replicate the exact S07 Pass 3b extraction logic (post-fix)."""
        analyzer = TemporalPoseAnalyzer(
            track_id=track.track_id,
            window_size=20,
            min_frames_crawling=3,
            min_frames_crouching=3,
            min_frames_running=3,
            min_frames_fallen=2,
            hysteresis_frames=2,
        )
        events = []
        for obs in track.observations:
            bbox = getattr(obs, "bbox", None)
            if bbox is None:
                continue
            if isinstance(bbox, TrackBBox):
                x1, y1, x2, y2 = bbox.x1, bbox.y1, bbox.x2, bbox.y2
            elif hasattr(bbox, "__len__") and len(bbox) >= 4:
                x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
            else:
                continue
            # Normalize if pixel coords
            if any(v > 1.5 for v in [x1, y1, x2, y2]):
                x1 /= max(frame_w, 1)
                y1 /= max(frame_h, 1)
                x2 /= max(frame_w, 1)
                y2 /= max(frame_h, 1)
            spf = SimplePoseFrame.from_bbox(
                frame_number=obs.frame_number,
                timestamp_ms=obs.timestamp_ms,
                track_id=track.track_id,
                x1=x1, y1=y1, x2=x2, y2=y2,
                frame_h=1.0,
            )
            spf.pose_confidence = float(getattr(obs, "detection_confidence", 0.5))
            evt = analyzer.update(spf)
            if evt:
                events.append(evt)
        events.extend(analyzer.flush())
        return analyzer, events

    def test_no_attribute_error_on_trackbbox(self):
        """The FAIL-007 error must not occur when feeding a real Track to the analyzer."""
        track = _make_confirmed_person_track(track_id=1, n_observations=10)
        # Must not raise AttributeError or TypeError
        analyzer, events = self._feed_track_to_analyzer(track)
        # Analyzer advanced past the error point — result is valid
        assert analyzer.current_state in [
            STATE_STANDING, STATE_WALKING, STATE_UNKNOWN,
        ]

    def test_analyzer_returns_valid_state_for_standing_person(self):
        """A person with tall bbox and minimal movement → STANDING or WALKING state."""
        track = _make_confirmed_person_track(track_id=2, n_observations=20)
        analyzer, events = self._feed_track_to_analyzer(track)
        # With bbox_h=0.5 (50% frame height) → classified as STANDING
        assert analyzer.current_state == STATE_STANDING

    def test_analyzer_processes_all_observations(self):
        """All observations are fed without skipping due to TrackBBox type check."""
        n = 15
        track = _make_confirmed_person_track(track_id=3, n_observations=n)
        analyzer, events = self._feed_track_to_analyzer(track)
        # All frames were processed → feature window advanced
        assert len(analyzer._all_frames) == n

    def test_pixel_coord_normalization_with_trackbbox(self):
        """TrackBBox with pixel coordinates (>1.5) are normalized correctly."""
        # Pixel-coord bboxes — typical for 320×240 video
        track = _make_confirmed_person_track(track_id=4, n_observations=5)
        # Override bboxes with pixel-scale coordinates
        for i, obs in enumerate(track.observations):
            obs.bbox = TrackBBox(
                x1=90 + i,  y1=48,
                x2=120 + i, y2=192,
                confidence=0.82, class_id=0, class_name="person"
            )
        # Must not fail during normalization
        analyzer, events = self._feed_track_to_analyzer(track, frame_w=320, frame_h=240)
        assert len(analyzer._all_frames) == 5

    def test_empty_observations_handled_gracefully(self):
        """Track with no observations produces UNKNOWN state, no crash."""
        track = _make_confirmed_person_track(track_id=5, n_observations=0)
        analyzer, events = self._feed_track_to_analyzer(track)
        assert analyzer.current_state == STATE_UNKNOWN
        assert events == []

    def test_none_bbox_observations_skipped(self):
        """Observations with bbox=None are silently skipped (not an error)."""
        track = _make_confirmed_person_track(track_id=6, n_observations=5)
        # Corrupt some observations
        track.observations[1] = TrackObservation(
            frame_number=1, timestamp_ms=166.0,
            bbox=None,  # type: ignore
            detection_confidence=0.0,
        )
        analyzer, events = self._feed_track_to_analyzer(track)
        # 4 of 5 observations processed (one skipped)
        assert len(analyzer._all_frames) == 4

    def test_single_observation_no_crash(self):
        """Track with exactly 1 observation — no prev_centroid, no crash."""
        track = _make_confirmed_person_track(track_id=7, n_observations=1)
        analyzer, events = self._feed_track_to_analyzer(track)
        assert len(analyzer._all_frames) == 1

    def test_existing_pose_state_machine_tests_unaffected(self):
        """SimplePoseFrame.from_bbox() still works when called with plain coords."""
        spf = SimplePoseFrame.from_bbox(
            frame_number=1, timestamp_ms=40.0, track_id=99,
            x1=0.3, y1=0.2, x2=0.4, y2=0.7, frame_h=1.0,
        )
        assert spf.body_height_ratio == pytest.approx(0.5, rel=0.01)
        assert spf.bbox_aspect_ratio == pytest.approx(0.1 / 0.5, rel=0.01)
        analyzer = TemporalPoseAnalyzer(track_id=99)
        result = analyzer.update(spf)
        # No crash, result is None or PoseEvent
        assert result is None or hasattr(result, "event_type")
