"""Video frame model — stores extracted frame metadata."""
import uuid
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class Frame(Base):
    """Represents a single extracted frame from a video."""
    __tablename__ = "frames"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id", ondelete="CASCADE"))
    frame_number: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_keyframe: Mapped[bool] = mapped_column(Boolean, default=False)
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    motion_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scene_change_score: Mapped[float | None] = mapped_column(Float, nullable=True)
