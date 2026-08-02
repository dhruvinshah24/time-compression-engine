"""Event graph node model."""
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class EventNode(Base):
    __tablename__ = "event_nodes"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id"))
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("videos.id"))
    node_type: Mapped[str]
    position: Mapped[int]
