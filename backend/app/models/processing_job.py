"""Processing job model."""
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"))
    status: Mapped[str]
