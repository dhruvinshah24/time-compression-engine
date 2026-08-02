"""
Motion Analyzer — Perception Engine, Phase 5.

Computes velocity, direction, speed class, and approach/recede signal
for every tracked object, using the track observation history from Phase 4.

Why centroid-based instead of optical flow:
  Phase 4 already gave us track objects with bbox histories.
  Centroid velocity is O(1) per observation pair and builds directly on
  that structured data. Dense optical flow would re-process raw pixels,
  discarding the tracking work we've already done.

  Optical flow is reserved for Phase 9 (camera motion compensation in
  shaky dashcam footage where centroid estimation proves insufficient).

Output:
  One MotionProfile per confirmed track, containing:
  - Instantaneous velocity vectors per frame
  - Smoothed velocity (rolling average)
  - Speed class: stationary / slow / walking / fast
  - Dominant direction: N / NE / E / SE / S / SW / W / NW / stationary
  - Approach/recede signal per frame
  - Camera motion flag per frame
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from app.engines.base import IntelligenceModule, ModuleHealth, ModuleMetrics
from app.engines.perception.motion_analyzer.config import MotionAnalyzerConfig
from app.engines.perception.tracker.track import Track, TrackObservation
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SpeedClass(str, Enum):
    STATIONARY = "stationary"
    SLOW = "slow"
    WALKING = "walking"
    FAST = "fast"
    UNKNOWN = "unknown"


class Direction(str, Enum):
    N = "N"
    NE = "NE"
    E = "E"
    SE = "SE"
    S = "S"
    SW = "SW"
    W = "W"
    NW = "NW"
    STATIONARY = "stationary"


class ApproachSignal(str, Enum):
    APPROACHING = "approaching"
    RECEDING = "receding"
    STABLE = "stable"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VelocityObservation:
    """Velocity computed between two consecutive track observations."""
    frame_number: int
    timestamp_ms: float
    dx: float           # normalized x displacement per ms
    dy: float           # normalized y displacement per ms
    speed: float        # magnitude of velocity (normalized units/ms)
    speed_per_second: float  # speed * 1000 (normalized units/second)
    angle_degrees: float    # atan2(dy, dx) in degrees, 0=right, CCW positive
    approach_signal: ApproachSignal
    bbox_area: float    # area of bounding box at this frame


@dataclass
class MotionProfile:
    """
    Complete motion analysis for one tracked object.

    Contains the full velocity time series plus summary statistics
    that downstream stages (Phase 6: Semantic Event Understanding) use
    to classify events like "person_running", "vehicle_approaching", etc.
    """
    track_id: int
    class_name: str
    observations: list[VelocityObservation] = field(default_factory=list)

    # Summary statistics (computed in finalize())
    dominant_speed_class: SpeedClass = SpeedClass.UNKNOWN
    dominant_direction: Direction = Direction.STATIONARY
    max_speed_per_second: float = 0.0
    avg_speed_per_second: float = 0.0
    is_stationary: bool = False
    has_approach_phase: bool = False
    has_recede_phase: bool = False
    total_displacement: float = 0.0   # straight-line start→end distance

    # Motion confidence [0.0, 1.0] — how reliable is this profile?
    # Computed from: track_length × detection_confidence × velocity_stability
    # Short tracks, noisy detections, and erratic velocity all reduce confidence.
    # This feeds directly into Phase 7 (Confidence Fusion).
    motion_confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "dominant_speed_class": self.dominant_speed_class.value,
            "dominant_direction": self.dominant_direction.value,
            "max_speed_per_second": round(self.max_speed_per_second, 6),
            "avg_speed_per_second": round(self.avg_speed_per_second, 6),
            "is_stationary": self.is_stationary,
            "has_approach_phase": self.has_approach_phase,
            "has_recede_phase": self.has_recede_phase,
            "total_displacement": round(self.total_displacement, 6),
            "motion_confidence": round(self.motion_confidence, 4),
            "observation_count": len(self.observations),
        }


@dataclass
class MotionAnalysisResult:
    """Complete motion analysis result for one video."""
    motion_profiles: dict[int, MotionProfile] = field(default_factory=dict)  # track_id → profile
    camera_motion_frames: list[int] = field(default_factory=list)
    stationary_track_count: int = 0
    moving_track_count: int = 0

    def to_metrics_dict(self) -> dict:
        return {
            "tracks_analyzed": len(self.motion_profiles),
            "stationary_tracks": self.stationary_track_count,
            "moving_tracks": self.moving_track_count,
            "camera_motion_frames": len(self.camera_motion_frames),
            "speed_class_distribution": self._speed_distribution(),
        }

    def _speed_distribution(self) -> dict[str, int]:
        dist: dict[str, int] = {}
        for profile in self.motion_profiles.values():
            key = profile.dominant_speed_class.value
            dist[key] = dist.get(key, 0) + 1
        return dist


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------

class MotionAnalyzer(IntelligenceModule):
    """
    Computes motion profiles for all confirmed tracks.

    Belongs to: Perception Engine
    Phase: 5 (implemented)

    Input:  TrackingResult from Phase 4
    Output: MotionAnalysisResult with one MotionProfile per confirmed track
    """

    name = "MotionAnalyzer"
    version = "0.5.0"
    engine = "Perception Engine"

    def __init__(self, config: MotionAnalyzerConfig | None = None) -> None:
        self.config = config or MotionAnalyzerConfig()
        self._calls_total = 0
        self._total_duration_ms = 0

    def analyze(self, tracks: list[Track]) -> MotionAnalysisResult:
        """
        Compute motion profiles for a list of tracks.

        Args:
            tracks: All tracks from TrackingResult (confirmed + ended).

        Returns:
            MotionAnalysisResult with per-track profiles and camera motion flags.
        """
        self._calls_total += 1
        start = time.perf_counter()

        # Only analyze confirmed tracks with enough observations
        confirmed = [
            t for t in tracks
            if t.is_confirmed and len(t.observations) >= 2
        ]

        profiles: dict[int, MotionProfile] = {}
        for track in confirmed:
            profile = self._build_profile(track)
            profiles[track.track_id] = profile

        # Camera motion detection: coherent velocity across all active tracks
        camera_motion_frames = self._detect_camera_motion(profiles)

        stationary = sum(1 for p in profiles.values() if p.is_stationary)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        self._total_duration_ms += elapsed_ms

        logger.info(
            "MotionAnalyzer: %d tracks analyzed, %d stationary, "
            "%d camera-motion frames in %dms",
            len(profiles), stationary, len(camera_motion_frames), elapsed_ms,
        )

        return MotionAnalysisResult(
            motion_profiles=profiles,
            camera_motion_frames=camera_motion_frames,
            stationary_track_count=stationary,
            moving_track_count=len(profiles) - stationary,
        )

    def _build_profile(self, track: Track) -> MotionProfile:
        """Build a MotionProfile from a single track's observations."""
        cfg = self.config
        profile = MotionProfile(
            track_id=track.track_id,
            class_name=track.class_name,
        )

        obs = track.observations
        velocity_obs: list[VelocityObservation] = []

        for i in range(1, len(obs)):
            prev = obs[i - 1]
            curr = obs[i]

            dt = curr.timestamp_ms - prev.timestamp_ms
            if dt <= 0:
                continue  # Same timestamp — skip (can happen with VFR)

            # Centroid positions (normalized coordinates)
            prev_cx = (prev.bbox.x1 + prev.bbox.x2) / 2
            prev_cy = (prev.bbox.y1 + prev.bbox.y2) / 2
            curr_cx = (curr.bbox.x1 + curr.bbox.x2) / 2
            curr_cy = (curr.bbox.y1 + curr.bbox.y2) / 2

            dx = curr_cx - prev_cx   # per ms
            dy = curr_cy - prev_cy   # per ms (positive = downward in image coords)

            speed = math.sqrt(dx * dx + dy * dy) / dt  # normalized units/ms
            speed_per_second = speed * 1000.0

            angle = math.degrees(math.atan2(-dy, dx))  # flip dy: up is positive

            # Approach/recede from bounding box area change
            prev_area = (prev.bbox.x2 - prev.bbox.x1) * (prev.bbox.y2 - prev.bbox.y1)
            curr_area = (curr.bbox.x2 - curr.bbox.x1) * (curr.bbox.y2 - curr.bbox.y1)
            approach = self._classify_approach(prev_area, curr_area)

            velocity_obs.append(VelocityObservation(
                frame_number=curr.frame_number,
                timestamp_ms=curr.timestamp_ms,
                dx=dx,
                dy=dy,
                speed=speed,
                speed_per_second=speed_per_second,
                angle_degrees=angle,
                approach_signal=approach,
                bbox_area=curr_area,
            ))

        profile.observations = velocity_obs

        if velocity_obs:
            self._finalize_profile(profile, track)

        return profile

    def _finalize_profile(self, profile: MotionProfile, track: Track) -> None:
        """Compute summary statistics from velocity observations."""
        cfg = self.config
        obs = profile.observations

        speeds = [o.speed_per_second for o in obs]
        profile.avg_speed_per_second = float(np.mean(speeds))
        profile.max_speed_per_second = float(np.max(speeds))

        # Dominant speed class based on median speed
        median_speed = float(np.median(speeds))
        profile.dominant_speed_class = self._classify_speed(median_speed)
        profile.is_stationary = profile.dominant_speed_class == SpeedClass.STATIONARY

        # Dominant direction based on mean angle of non-stationary frames
        moving_angles = [
            o.angle_degrees for o in obs
            if o.speed_per_second > cfg.speed_stationary_max * 1.5
        ]
        if moving_angles:
            profile.dominant_direction = self._classify_direction(
                float(np.degrees(np.arctan2(
                    np.mean(np.sin(np.radians(moving_angles))),
                    np.mean(np.cos(np.radians(moving_angles))),
                )))
            )

        # Total displacement (start bbox center → end bbox center)
        first = profile.observations[0]
        last = profile.observations[-1]
        # Approximate from cumulative dx/dy
        total_dx = sum(o.dx * 1.0 for o in obs)  # dx is per ms, rough proxy
        total_dy = sum(o.dy * 1.0 for o in obs)
        profile.total_displacement = math.sqrt(total_dx ** 2 + total_dy ** 2)

        # Approach/recede phases
        profile.has_approach_phase = any(
            o.approach_signal == ApproachSignal.APPROACHING for o in obs
        )
        profile.has_recede_phase = any(
            o.approach_signal == ApproachSignal.RECEDING for o in obs
        )

        # Motion confidence — how reliable is this profile?
        # Factor 1: track length (10 matched frames = fully length-confident)
        length_factor = min(len(obs) / 10.0, 1.0)

        # Factor 2: velocity stability (inverse coefficient of variation)
        # CV = std/mean. Low CV → consistent motion → high stability.
        # Stationary tracks get stability=1.0 (stable means of "not moving").
        if len(speeds) >= 2:
            mean_s = float(np.mean(speeds))
            std_s = float(np.std(speeds))
            cv = std_s / (mean_s + 1e-8)
            stability_factor = 1.0 / (1.0 + cv)
        else:
            stability_factor = 0.5  # unknown — single observation pair

        # Factor 3: average detection confidence from source observations
        det_confidences = [o.detection_confidence for o in track.observations if o.detection_confidence > 0]
        det_confidence = float(np.mean(det_confidences)) if det_confidences else 0.8

        profile.motion_confidence = float(np.clip(
            0.4 * length_factor + 0.4 * det_confidence + 0.2 * stability_factor,
            0.0, 1.0,
        ))

    def _classify_speed(self, speed_per_second: float) -> SpeedClass:
        cfg = self.config
        if speed_per_second < cfg.speed_stationary_max:
            return SpeedClass.STATIONARY
        if speed_per_second < cfg.speed_slow_max:
            return SpeedClass.SLOW
        if speed_per_second < cfg.speed_walking_max:
            return SpeedClass.WALKING
        return SpeedClass.FAST

    def _classify_direction(self, angle_degrees: float) -> Direction:
        """Map angle (degrees, 0=right, CCW) to 8-compass direction."""
        # Normalize to [0, 360)
        angle = angle_degrees % 360
        # 8 sectors of 45 degrees each, starting at 22.5
        sectors = [
            (22.5, Direction.E), (67.5, Direction.NE), (112.5, Direction.N),
            (157.5, Direction.NW), (202.5, Direction.W), (247.5, Direction.SW),
            (292.5, Direction.S), (337.5, Direction.SE),
        ]
        for threshold, direction in sectors:
            if angle < threshold:
                return direction
        return Direction.E  # wraps around: >337.5 is E

    def _classify_approach(self, prev_area: float, curr_area: float) -> ApproachSignal:
        if prev_area <= 0:
            return ApproachSignal.STABLE
        change = (curr_area - prev_area) / prev_area
        if change > self.config.area_change_threshold:
            return ApproachSignal.APPROACHING
        if change < -self.config.area_change_threshold:
            return ApproachSignal.RECEDING
        return ApproachSignal.STABLE

    def _detect_camera_motion(
        self,
        profiles: dict[int, MotionProfile],
    ) -> list[int]:
        """
        Detect frames where camera motion dominates.

        Camera motion: most/all tracks move in the same direction in the same frame.
        Detected by computing mean velocity coherence across tracks per frame.

        Returns list of frame numbers flagged as camera-motion-dominated.
        """
        cfg = self.config
        if len(profiles) < cfg.min_tracks_for_camera_motion:
            return []

        # Build frame → list of (dx, dy) across all tracks
        frame_velocities: dict[int, list[tuple[float, float]]] = {}
        for profile in profiles.values():
            for obs in profile.observations:
                frame_velocities.setdefault(obs.frame_number, []).append((obs.dx, obs.dy))

        camera_frames: list[int] = []
        for frame_number, velocities in frame_velocities.items():
            if len(velocities) < cfg.min_tracks_for_camera_motion:
                continue
            coherence = self._velocity_coherence(velocities)
            if coherence > cfg.camera_motion_coherence_threshold:
                camera_frames.append(frame_number)

        return sorted(camera_frames)

    def _velocity_coherence(self, velocities: list[tuple[float, float]]) -> float:
        """
        Compute cosine similarity of velocity vectors.

        1.0 = all pointing same direction (camera motion).
        0.0 = random directions (real independent object motion).
        """
        if len(velocities) < 2:
            return 0.0

        vecs = np.array(velocities, dtype=np.float64)
        # Normalize each vector
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        # Filter out near-zero vectors (stationary objects)
        mask = norms[:, 0] > 1e-8
        if mask.sum() < 2:
            return 0.0
        unit_vecs = vecs[mask] / norms[mask]

        # Mean vector coherence: if all same direction, mean norm ≈ 1
        mean_vec = unit_vecs.mean(axis=0)
        coherence = float(np.linalg.norm(mean_vec))
        return min(1.0, coherence)

    async def process(self, context: PipelineContext) -> StageResult:
        from app.pipeline.stages import s06_motion_analyze
        return await s06_motion_analyze.run(context)

    def health_check(self) -> ModuleHealth:
        return ModuleHealth.READY  # Pure Python + NumPy — always available

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
