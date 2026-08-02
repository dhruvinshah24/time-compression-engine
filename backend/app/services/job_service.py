"""
Job service — Time Compression Engine.

Manages processing job lifecycle: creation, status updates, cancellation,
and cleanup. Phase 1 stub: all methods are unimplemented.

Phase 3 will wire this to the jobs repository, Celery task queue, and
pipeline orchestrator for async processing.
"""

import logging

logger = logging.getLogger(__name__)


# TODO(Phase 3): implement job lifecycle management
# Methods to implement:
#   - create_job(video_id, settings) -> ProcessingJobSchema
#   - get_job(job_id) -> ProcessingJobSchema | None
#   - cancel_job(job_id) -> bool
#   - list_jobs(page, limit) -> list[ProcessingJobSchema]
#   - get_job_stages(job_id) -> list[PipelineStageSchema]
