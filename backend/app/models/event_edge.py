"""Event graph edge model."""
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey
from app.db.base import Base

class EventEdge(Base):
    __tablename__ = "event_edges"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    from_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_nodes.id"))
    to_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("event_nodes.id"))
    relationship: Mapped[str]
    weight: Mapped[float]
