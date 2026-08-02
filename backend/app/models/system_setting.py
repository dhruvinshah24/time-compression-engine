"""System setting model."""
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
    data_type: Mapped[str]
    description: Mapped[str]
    category: Mapped[str]
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
