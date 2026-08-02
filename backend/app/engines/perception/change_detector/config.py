"""Configuration for the Scene Change Detector module."""
from dataclasses import dataclass, field


@dataclass
class SceneChangeConfig:
    """
    Configuration for Phase 3A Scene Change Detection.

    All thresholds are in the composite score range [0.0, 1.0].
    Lower = more sensitive (more boundaries detected).
    Higher = less sensitive (fewer boundaries detected).

    Research notes:
    - hard_cut_threshold: Rarely needs tuning. 0.7 works across all tested domains.
    - adaptive_k: The most impactful parameter. Increase for noisy cameras.
    - histogram_weight + pixel_weight must sum to 1.0.
    """
    # Composite score weights
    pixel_weight: float = 0.4
    histogram_weight: float = 0.6

    # Adaptive threshold parameters
    adaptive_window: int = 50       # Number of frames in rolling stats window
    adaptive_k: float = 1.5         # Sensitivity: threshold = mean + k * std

    # Hard cut threshold (overrides adaptive — always a scene boundary)
    hard_cut_threshold: float = 0.70

    # Duplicate frame threshold (skip downstream processing)
    duplicate_threshold: float = 0.02

    # Histogram parameters
    histogram_bins: int = 16        # Bins per HSV channel

    # Output control
    min_scene_duration_frames: int = 3   # Ignore boundaries < N frames apart
    include_duplicate_frames: bool = False  # Whether to include duplicates in output

    def __post_init__(self) -> None:
        if abs(self.pixel_weight + self.histogram_weight - 1.0) > 1e-6:
            raise ValueError(
                f"pixel_weight + histogram_weight must equal 1.0, "
                f"got {self.pixel_weight + self.histogram_weight}"
            )
        if self.adaptive_window < 5:
            raise ValueError("adaptive_window must be >= 5")
        if not 0.0 < self.hard_cut_threshold <= 1.0:
            raise ValueError("hard_cut_threshold must be in (0, 1]")
