"""
Video metadata utilities — Time Compression Engine.

Provides helpers for reading technical metadata from video files using
FFprobe. All functions are stub-safe: they return None or sensible defaults
if FFprobe is unavailable, and log a WARNING rather than raising.

Phase 3 implementation will replace these stubs with real FFprobe calls.
"""

import logging

logger = logging.getLogger(__name__)


def get_video_metadata(video_path: str) -> dict | None:
    """
    Return basic video metadata (duration, fps, resolution, codec).

    Args:
        video_path: Absolute path to the video file.

    Returns:
        Dict with keys: duration_seconds, fps, width, height, codec.
        Returns None if the file cannot be probed.

    Note: Phase 1 stub — returns None. Phase 3 will implement FFprobe.
    """
    # TODO(Phase 3): implement via ffprobe -v quiet -print_format json
    logger.debug("[STUB] get_video_metadata not yet implemented — Phase 3")
    return None


def get_frame_count(video_path: str) -> int | None:
    """
    Return the total frame count of a video file.

    Returns None if the frame count cannot be determined.

    Note: Phase 1 stub — returns None. Phase 3 will implement FFprobe.
    """
    # TODO(Phase 3): implement via ffprobe nb_frames or duration * fps
    logger.debug("[STUB] get_frame_count not yet implemented — Phase 3")
    return None
