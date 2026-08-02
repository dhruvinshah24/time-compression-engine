"""Schema for EventNode."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class EventNodeBase(BaseModel):
    pass

class EventNodeCreate(EventNodeBase):
    pass

class EventNodeResponse(EventNodeBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
