"""Database initialization and seeding."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_setting import SystemSetting
from sqlalchemy import select

# ── Default pipeline seed values ─────────────────────────────────────────────
# These are the v1.0.0 reference defaults that match TCE_V1_REFERENCE in
# app/evaluation/reference_config.py. Change them there first, then mirror here.
_DEFAULT_FRAME_SKIP_RATE           = "5"       # Extract every 5th frame
_DEFAULT_MIN_MOTION_THRESHOLD      = "15.0"    # Motion magnitude threshold (pixels/frame)
_DEFAULT_DETECTION_CONFIDENCE      = "0.72"    # Object detection confidence floor
_DEFAULT_OUTPUT_FPS                = "24"      # Highlight reel frame rate
_DEFAULT_MIN_EVENT_DURATION_MS     = "1000"    # Ignore sub-second detections
_DEFAULT_MAX_EVENTS_PER_HOUR       = "200"     # Safety cap for event density
_DEFAULT_STORY_GAP_THRESHOLD_MS    = "5000"    # Max gap to bridge narrative chains
_DEFAULT_NARRATIVE_MIN_CHAIN_LEN   = "2"       # Minimum events to form a story chain
_DEFAULT_COMPRESSION_POLICY        = "narrative_aware"
_DEFAULT_EXPLAINABILITY_ENABLED    = "true"


async def init_db(db: AsyncSession):
    """Seed initial system settings if the table is empty."""
    result = await db.execute(select(SystemSetting))
    if not result.scalars().first():
        settings = [
            SystemSetting(key="frame_skip_rate",          value=_DEFAULT_FRAME_SKIP_RATE,         data_type="int",    description="Number of frames to skip during extraction",                      category="pipeline"),
            SystemSetting(key="min_motion_threshold",     value=_DEFAULT_MIN_MOTION_THRESHOLD,    data_type="float",  description="Minimum motion vector magnitude to trigger analysis",            category="detection"),
            SystemSetting(key="detection_confidence",     value=_DEFAULT_DETECTION_CONFIDENCE,    data_type="float",  description="Object/event detection confidence threshold (0-1)",             category="detection"),
            SystemSetting(key="output_fps",               value=_DEFAULT_OUTPUT_FPS,              data_type="int",    description="Frame rate of the exported highlight reel",                     category="export"),
            SystemSetting(key="min_event_duration_ms",    value=_DEFAULT_MIN_EVENT_DURATION_MS,   data_type="int",    description="Minimum event duration to register (milliseconds)",             category="detection"),
            SystemSetting(key="max_events_per_hour",      value=_DEFAULT_MAX_EVENTS_PER_HOUR,     data_type="int",    description="Maximum events per hour (safety cap)",                          category="detection"),
            SystemSetting(key="story_gap_threshold_ms",   value=_DEFAULT_STORY_GAP_THRESHOLD_MS,  data_type="int",    description="Max gap between events to link into a narrative chain (ms)",    category="temporal"),
            SystemSetting(key="narrative_min_chain_length",value=_DEFAULT_NARRATIVE_MIN_CHAIN_LEN,data_type="int",    description="Minimum events required to form a story chain",                 category="temporal"),
            SystemSetting(key="compression_policy",       value=_DEFAULT_COMPRESSION_POLICY,      data_type="string", description="Compression strategy: narrative_aware | max_compression | all_events", category="temporal"),
            SystemSetting(key="explainability_enabled",   value=_DEFAULT_EXPLAINABILITY_ENABLED,  data_type="bool",   description="Whether to generate explainability manifests",                  category="semantic"),
        ]
        db.add_all(settings)
        await db.commit()
