"""
Multi-Object Tracker — Perception Engine, Phase 4.

Maintains consistent object identities across video frames.

Core Algorithm: IoU-based Hungarian matching with Track lifecycle states.
Full rationale: research/algorithms.md → Phase 4 section (to be added).

The tracker answers: "Is the person in frame 47 the same person as in frame 52?"

Design:
- One tracker instance per job (stateful — holds all active tracks).
- Each call to update() processes one frame's detections.
- Returns the full list of tracks (active + lost) after update.
- Track IDs are globally unique: increments monotonically from 1.
- Completely decoupled from the detection model (any Detection source works).

Upgrade path (Phase 9):
- Replace IoU matching with Mahalanobis distance + Kalman filter (SORT).
- Add appearance embeddings for re-identification (DeepSORT).
- The Track and TrackState data models don't need to change.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.perception.tracker.config import TrackerConfig
from app.engines.perception.tracker.iou import compute_iou_matrix, hungarian_match
from app.engines.perception.tracker.track import Track, TrackBBox, TrackState
from app.model_registry.base_model import FrameDetectionResult
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


@dataclass
class TrackingResult:
    """Complete tracking result for a sequence of frames."""
    total_frames_processed: int = 0
    total_tracks_created: int = 0
    active_tracks: list[Track] = field(default_factory=list)
    ended_tracks: list[Track] = field(default_factory=list)
    all_tracks: list[Track] = field(default_factory=list)
    per_frame_track_counts: list[int] = field(default_factory=list)

    @property
    def confirmed_tracks(self) -> list[Track]:
        return [t for t in self.all_tracks if t.is_confirmed]

    @property
    def avg_track_length_frames(self) -> float:
        if not self.all_tracks:
            return 0.0
        return sum(t.total_frames_matched for t in self.all_tracks) / len(self.all_tracks)

    @property
    def avg_track_confidence(self) -> float:
        tracks = [t for t in self.all_tracks if t.observations]
        if not tracks:
            return 0.0
        return sum(t.avg_confidence for t in tracks) / len(tracks)

    def to_metrics_dict(self) -> dict:
        return {
            "total_frames_processed": self.total_frames_processed,
            "total_tracks_created": self.total_tracks_created,
            "active_tracks": len(self.active_tracks),
            "ended_tracks": len(self.ended_tracks),
            "confirmed_tracks": len(self.confirmed_tracks),
            "avg_track_length_frames": round(self.avg_track_length_frames, 2),
            "avg_track_confidence": round(self.avg_track_confidence, 4),
            "classes_tracked": self._classes_tracked(),
        }

    def _classes_tracked(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for track in self.all_tracks:
            counts[track.class_name] = counts.get(track.class_name, 0) + 1
        return counts


class MultiObjectTracker(IntelligenceModule):
    """
    IoU-based multi-object tracker with full track lifecycle management.

    Belongs to: Perception Engine
    Phase: 4 (implemented)

    Algorithm: Hungarian matching on IoU matrix.
    - O(n³) assignment per frame (n = max(tracks, detections)).
    - Tentative state prevents false tracks from noise.
    - Lost state handles brief occlusions (N frames tolerance).
    - Ended state permanently closes tracks for the event graph.

    The tracker is stateful. One instance handles one full video.
    Reset between videos or create a new instance.

    Usage:
        tracker = MultiObjectTracker()
        for frame_result in frame_detection_results:
            tracks = tracker.update(frame_result)
        final_result = tracker.finalize()
    """

    name = "MultiObjectTracker"
    version = "0.4.0"
    engine = "Perception Engine"

    def __init__(self, config: TrackerConfig | None = None) -> None:
        self.config = config or TrackerConfig()
        self._tracks: dict[int, Track] = {}   # track_id → Track
        self._next_id: int = 1
        self._frames_processed: int = 0
        self._calls_total: int = 0
        self._total_duration_ms: int = 0

    def update(self, frame_result: FrameDetectionResult) -> list[Track]:
        """
        Process one frame's detections and update all tracks.

        Steps:
        1. Build current bboxes from active/lost tracks
        2. Compute IoU matrix between tracks and detections
        3. Run Hungarian matching
        4. Update matched tracks
        5. Increment lost_frames for unmatched tracks; end if exceeded limit
        6. Create new tentative tracks for unmatched detections
        7. Confirm tentative tracks that have enough matches

        Args:
            frame_result: FrameDetectionResult from the ObjectDetector.

        Returns:
            All currently ACTIVE and LOST tracks after this update.
        """
        frame_number = frame_result.frame_number
        timestamp_ms = frame_result.timestamp_ms
        detections = frame_result.detections
        self._frames_processed += 1

        # Tracks eligible for matching (not ENDED or too-tentative)
        candidate_tracks = [
            t for t in self._tracks.values()
            if t.state in (TrackState.TENTATIVE, TrackState.ACTIVE, TrackState.LOST)
        ]

        # ── Step 1: IoU matching ───────────────────────────────────────────
        if candidate_tracks and detections:
            track_boxes = [
                (t.current_bbox.x1, t.current_bbox.y1,
                 t.current_bbox.x2, t.current_bbox.y2)
                for t in candidate_tracks if t.current_bbox
            ]
            det_boxes = [
                (d.bbox_x1, d.bbox_y1, d.bbox_x2, d.bbox_y2)
                for d in detections
            ]

            iou_matrix = compute_iou_matrix(track_boxes, det_boxes)
            matched, unmatched_tracks, unmatched_dets = hungarian_match(
                iou_matrix, iou_threshold=self.config.iou_threshold
            )
        else:
            matched = []
            unmatched_tracks = list(range(len(candidate_tracks)))
            unmatched_dets = list(range(len(detections)))

        # ── Step 2: Update matched tracks ─────────────────────────────────
        for track_idx, det_idx in matched:
            track = candidate_tracks[track_idx]
            det = detections[det_idx]
            bbox = TrackBBox(
                x1=det.bbox_x1, y1=det.bbox_y1,
                x2=det.bbox_x2, y2=det.bbox_y2,
                confidence=det.confidence,
                class_id=det.class_id,
                class_name=det.class_name,
            )
            track.update(frame_number, timestamp_ms, bbox)

            # Tentative → Active after enough consecutive matches
            if (track.state == TrackState.TENTATIVE
                    and track.total_frames_matched >= self.config.min_confirmation_frames):
                track.state = TrackState.ACTIVE
                track.confirmed_at_frame = frame_number

            # Lost → Active on re-match
            elif track.state == TrackState.LOST:
                track.state = TrackState.ACTIVE

        # ── Step 3: Handle unmatched tracks ───────────────────────────────
        for track_idx in unmatched_tracks:
            track = candidate_tracks[track_idx]
            track.mark_lost()

            if track.state == TrackState.TENTATIVE:
                # Tentative tracks end quickly — never confirmed
                if track.lost_frames >= 1:
                    track.end()
            elif track.lost_frames > self.config.max_lost_frames:
                track.end()
            else:
                track.state = TrackState.LOST

        # ── Step 4: Create new tracks for unmatched detections ────────────
        for det_idx in unmatched_dets:
            det = detections[det_idx]
            # Skip very low confidence detections for track creation
            if det.confidence < self.config.min_detection_confidence:
                continue

            bbox = TrackBBox(
                x1=det.bbox_x1, y1=det.bbox_y1,
                x2=det.bbox_x2, y2=det.bbox_y2,
                confidence=det.confidence,
                class_id=det.class_id,
                class_name=det.class_name,
            )
            track = Track(
                track_id=self._next_id,
                class_name=det.class_name,
                class_id=det.class_id,
                state=TrackState.TENTATIVE,
                created_frame=frame_number,
                created_timestamp_ms=timestamp_ms,
                last_seen_frame=frame_number,
                last_seen_timestamp_ms=timestamp_ms,
                current_bbox=bbox,
            )
            track.update(frame_number, timestamp_ms, bbox)
            self._tracks[self._next_id] = track
            self._next_id += 1

        # Return only non-ended tracks
        return [
            t for t in self._tracks.values()
            if t.state != TrackState.ENDED
        ]

    def finalize(self) -> TrackingResult:
        """
        Close all remaining open tracks and return the final result.

        Call after all frames have been processed.
        """
        # End any tracks still LOST at end of video
        for track in self._tracks.values():
            if track.state in (TrackState.LOST, TrackState.TENTATIVE):
                track.end()

        all_tracks = list(self._tracks.values())
        active = [t for t in all_tracks if t.state == TrackState.ACTIVE]
        ended = [t for t in all_tracks if t.state == TrackState.ENDED]

        return TrackingResult(
            total_frames_processed=self._frames_processed,
            total_tracks_created=len(all_tracks),
            active_tracks=active,
            ended_tracks=ended,
            all_tracks=all_tracks,
        )

    def reset(self) -> None:
        """Reset tracker state for a new video."""
        self._tracks.clear()
        self._next_id = 1
        self._frames_processed = 0

    async def process(self, context: PipelineContext) -> StageResult:
        """IntelligenceModule contract — delegates to s05_track stage."""
        from app.pipeline.stages import s05_track
        return await s05_track.run(context)

    def health_check(self) -> ModuleHealth:
        try:
            from scipy.optimize import linear_sum_assignment  # noqa: F401
            return ModuleHealth.READY
        except ImportError:
            return ModuleHealth.UNAVAILABLE

    def get_metrics(self) -> ModuleMetrics:
        return ModuleMetrics(
            name=self.name,
            version=self.version,
            engine=self.engine,
            calls_total=self._calls_total,
            avg_duration_ms=(
                self._total_duration_ms / self._calls_total
                if self._calls_total > 0 else 0.0
            ),
            last_health=self.health_check(),
        )
