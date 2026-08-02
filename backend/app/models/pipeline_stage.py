"""Pipeline stage tracking model — one row per stage per processing job."""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base
import enum

class StageStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class PipelineStage(Base):
    """Tracks the status and metrics of each stage in a processing job."""
    __tablename__ = "pipeline_stages"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"))
    stage_name: Mapped[str] = mapped_column(String(64), nullable=False)
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StageStatus] = mapped_column(SAEnum(StageStatus), default=StageStatus.PENDING)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    artifacts: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    logs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    engine: Mapped[str | None] = mapped_column(String(64), nullable=True)
