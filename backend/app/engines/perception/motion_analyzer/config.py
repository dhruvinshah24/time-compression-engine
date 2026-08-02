"""Configuration for the Motion Analyzer module."""
from dataclasses import dataclass


@dataclass
class MotionAnalyzerConfig:
    """
    Configuration for Phase 5 Motion Analysis.

    Speed thresholds are in normalized coordinate units per second.
    "Normalized" means relative to the frame dimensions (0.0–1.0 range).
    A value of 0.10 means the object moves 10% of the frame width per second.

    Calibration note:
    These defaults are tuned for surveillance CCTV at 5 extracted FPS
    (frame_skip_rate=5 at 25fps source). If your extraction rate changes,
    re-evaluate the speed thresholds against the benchmark corpus.

    area_change_threshold:
        Fractional area change required to classify approach/recede.
        0.05 = 5% area change per observation pair.
        Larger → less sensitive (misses slow approaches).
        Smaller → more sensitive (more false detections from bbox jitter).

    camera_motion_coherence_threshold:
        Minimum cosine similarity of velocity vectors across all tracks
        to classify a frame as dominated by camera motion.
        0.85 = 85% directional agreement among tracks.
    """
    # Speed classification thresholds (normalized units/second)
    speed_stationary_max: float = 0.01
    speed_slow_max: float = 0.05
    speed_walking_max: float = 0.15
    # speed >= walking_max is classified as "fast"

    # Approach/recede detection
    area_change_threshold: float = 0.05

    # Camera motion detection
    camera_motion_coherence_threshold: float = 0.85
    min_tracks_for_camera_motion: int = 3   # need at least N tracks to declare camera motion

    # Smoothing — use rolling average over N observations for velocity
    velocity_smoothing_window: int = 3
