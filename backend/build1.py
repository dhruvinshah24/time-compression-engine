import os
from pathlib import Path

base = Path(r"C:\Users\dhruv\.gemini\antigravity\scratch\time-compression-engine\backend")

def write_file(path_str, content):
    p = base / path_str
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")

# Root Files
write_file("requirements.txt", """
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
sqlalchemy>=2.0.30
asyncpg>=0.29.0
alembic>=1.13.1
python-multipart>=0.0.9
aiofiles>=23.2.1
structlog>=24.2.0
celery>=5.3.6
redis>=5.0.4
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
httpx>=0.27.0
pytest>=8.2.0
pytest-asyncio>=0.23.7
""")

write_file("Dockerfile", """
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
""")

write_file(".env.example", """
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tce
""")

write_file("alembic.ini", """
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/tce
""")

# Core
write_file("app/core/config.py", """
\"\"\"Configuration settings.\"\"\"
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Time Compression Engine API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tce"
    
    class Config:
        env_file = ".env"

settings = Settings()
""")

write_file("app/core/logging.py", """
\"\"\"Structured logging configuration.\"\"\"
import structlog
import logging

def setup_logging():
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
""")

write_file("app/core/security.py", """
\"\"\"Security utilities.\"\"\"
# Stub for security functions
def get_password_hash(password: str) -> str:
    return password + "hash"
""")

# DB
write_file("app/db/base.py", """
\"\"\"Database base model.\"\"\"
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
""")

write_file("app/db/session.py", """
\"\"\"Database session management.\"\"\"
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
""")

write_file("app/db/init_db.py", """
\"\"\"Database initialization and seeding.\"\"\"
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_setting import SystemSetting
from sqlalchemy import select

async def init_db(db: AsyncSession):
    \"\"\"Seed initial settings if empty.\"\"\"
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
""")

# Models
write_file("app/models/__init__.py", "")

write_file("app/models/user.py", """
\"\"\"User model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]
""")

write_file("app/models/video.py", """
\"\"\"Video model.\"\"\"
import uuid
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Video(Base):
    __tablename__ = "videos"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str]
    duration_seconds: Mapped[float]
    fps: Mapped[float]
    resolution_width: Mapped[int]
    resolution_height: Mapped[int]
    codec: Mapped[str]
    size_bytes: Mapped[int]
    frame_count: Mapped[int]
    avg_brightness: Mapped[float | None]
    avg_motion_score: Mapped[float | None]
    camera_angle: Mapped[str | None]
    scene_type: Mapped[str | None]  # indoor/outdoor/unknown
    time_of_day: Mapped[str | None] # day/night/unknown
    recording_date: Mapped[date | None]
    source_domain: Mapped[str | None]
    status: Mapped[str] # uploading/queued/processing/done/failed
""")

write_file("app/models/processing_job.py", """
\"\"\"Processing job model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"))
    status: Mapped[str]
""")

write_file("app/models/pipeline_stage.py", """
\"\"\"Pipeline stage model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class PipelineStage(Base):
    __tablename__ = "pipeline_stages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processing_jobs.id"))
    stage_name: Mapped[str]
    status: Mapped[str]
""")

write_file("app/models/frame.py", """
\"\"\"Frame model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class Frame(Base):
    __tablename__ = "frames"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"))
    timestamp_ms: Mapped[int]
""")

write_file("app/models/detected_object.py", """
\"\"\"Detected object model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class DetectedObject(Base):
    __tablename__ = "detected_objects"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    frame_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("frames.id"))
    label: Mapped[str]
    confidence: Mapped[float]
""")

write_file("app/models/event.py", """
\"\"\"Event model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base

class Event(Base):
    __tablename__ = "events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"))
    event_type: Mapped[str]
    start_time_ms: Mapped[int]
    end_time_ms: Mapped[int]
    confidence: Mapped[float]
    importance_rank: Mapped[int | None]
    description: Mapped[str | None]
    objects_involved: Mapped[dict | None] = mapped_column(type_=JSONB)
    roi_region: Mapped[dict | None] = mapped_column(type_=JSONB)
    explanation: Mapped[dict | None] = mapped_column(type_=JSONB)
    story_sequence_id: Mapped[uuid.UUID | None]
    thumbnail_path: Mapped[str | None]
    clip_path: Mapped[str | None]
""")

write_file("app/models/event_node.py", """
\"\"\"Event graph node model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class EventNode(Base):
    __tablename__ = "event_nodes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"))
    node_type: Mapped[str] # start/intermediate/end
    position: Mapped[int]
""")

write_file("app/models/event_edge.py", """
\"\"\"Event graph edge model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class EventEdge(Base):
    __tablename__ = "event_edges"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    from_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_nodes.id"))
    to_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_nodes.id"))
    relationship: Mapped[str] # caused_by/followed_by/concurrent/implies
    weight: Mapped[float]
""")

write_file("app/models/ai_summary.py", """
\"\"\"AI summary model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class AISummary(Base):
    __tablename__ = "ai_summaries"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"))
    summary_text: Mapped[str]
""")

write_file("app/models/system_setting.py", """
\"\"\"System setting model.\"\"\"
import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from sqlalchemy import func

class SystemSetting(Base):
    __tablename__ = "system_settings"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(unique=True, index=True)
    value: Mapped[str]
    data_type: Mapped[str] # string/int/float/bool
    description: Mapped[str]
    category: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
""")

write_file("app/models/system_log.py", """
\"\"\"System log model.\"\"\"
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class SystemLog(Base):
    __tablename__ = "system_logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    level: Mapped[str]
    message: Mapped[str]
""")

print("Build 1 complete")
