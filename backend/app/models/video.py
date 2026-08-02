"""Video model."""
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
    scene_type: Mapped[str | None]
    time_of_day: Mapped[str | None]
    recording_date: Mapped[date | None]
    source_domain: Mapped[str | None]
    status: Mapped[str]
