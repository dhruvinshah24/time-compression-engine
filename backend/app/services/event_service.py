"""
Event service — Time Compression Engine.

Provides business logic for querying, filtering, and exporting event data.
Phase 1 stub: all methods are unimplemented. Phase 4 will add full query
logic backed by the events repository and narrative context.
"""

import logging

logger = logging.getLogger(__name__)


# TODO(Phase 4): implement event business logic
# Methods to implement:
#   - list_events(job_id, filters) -> list[EventSchema]
#   - get_event(event_id) -> EventSchema | None
#   - get_event_explanation(event_id) -> ExplainabilityManifest | None
#   - export_events(job_id, format) -> bytes
