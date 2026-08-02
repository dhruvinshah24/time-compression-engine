"""Schema for EventEdge."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class EventEdgeBase(BaseModel):
    pass

class EventEdgeCreate(EventEdgeBase):
    pass

class EventEdgeResponse(EventEdgeBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
