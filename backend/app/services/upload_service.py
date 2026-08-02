"""
Upload service — Time Compression Engine.

Handles video file intake: validation, storage, and job initialisation.
Phase 1 stub: all methods are unimplemented.

Phase 2 will implement streaming upload to local storage with sha256
integrity check, followed by automatic job creation.
"""

import logging

logger = logging.getLogger(__name__)


# TODO(Phase 2): implement upload intake pipeline
# Methods to implement:
#   - receive_upload(file, domain, metadata) -> VideoSchema
#   - validate_video_file(path) -> ValidationResult
#   - compute_checksum(path) -> str
