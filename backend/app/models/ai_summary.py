"""AI Summary model — stores generated video summaries and compression statistics."""
import uuid
from datetime import datetime
from sqlalchemy import String, Float, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class AISummary(Base):
    """Stores AI-generated summary and compression metrics for a processed video."""
    __tablename__ = "ai_summaries"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"))
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    compression_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    events_included: Mapped[int] = mapped_column(Integer, default=0)
    events_excluded: Mapped[int] = mapped_column(Integer, default=0)
    narrative_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
