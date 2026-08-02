"""Detected object model — stores per-frame object detection results."""
import uuid
from sqlalchemy import String, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base

class DetectedObject(Base):
    """Represents an object detected in a single video frame."""
    __tablename__ = "detected_objects"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    frame_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("frames.id", ondelete="CASCADE"))
    class_name: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # {x, y, w, h}
    track_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
