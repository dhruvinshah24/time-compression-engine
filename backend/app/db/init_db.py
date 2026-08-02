"""Database initialization and seeding."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_setting import SystemSetting
from sqlalchemy import select

async def init_db(db: AsyncSession):
    """Seed initial settings if empty."""
    result = await db.execute(select(SystemSetting))
    if not result.scalars().first():
        settings = [
            SystemSetting(key="frame_skip_rate", value="5", data_type="int", description="", category="pipeline"),
            SystemSetting(key="min_motion_threshold", value="15.0", data_type="float", description="", category="detection"),
            SystemSetting(key="detection_confidence", value="0.72", data_type="float", description="", category="detection"),
            SystemSetting(key="output_fps", value="24", data_type="int", description="", category="export"),
            SystemSetting(key="min_event_duration_ms", value="1000", data_type="int", description="", category="detection"),
            SystemSetting(key="max_events_per_hour", value="200", data_type="int", description="", category="detection"),
            SystemSetting(key="story_gap_threshold_ms", value="5000", data_type="int", description="", category="temporal"),
            SystemSetting(key="narrative_min_chain_length", value="2", data_type="int", description="", category="temporal"),
            SystemSetting(key="compression_policy", value="narrative_aware", data_type="string", description="", category="temporal"),
            SystemSetting(key="explainability_enabled", value="true", data_type="bool", description="", category="semantic")
        ]
        db.add_all(settings)
        await db.commit()
