"""Schema for Event."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class EventBase(BaseModel):
    pass

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
