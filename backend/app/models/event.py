"""Event model."""
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
