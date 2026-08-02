"""
Video service — Time Compression Engine.

Provides business logic for managing video records, metadata enrichment,
and search. Phase 1 stub: all methods are unimplemented.

Phase 3 will implement full CRUD backed by the video repository plus
FFprobe-driven metadata extraction via app.utils.video_meta.
"""

import logging

logger = logging.getLogger(__name__)


# TODO(Phase 3): implement video management logic
# Methods to implement:
#   - list_videos(page, limit) -> list[VideoSchema]
#   - get_video(video_id) -> VideoSchema | None
#   - delete_video(video_id) -> bool
#   - enrich_metadata(video_id) -> VideoSchema
