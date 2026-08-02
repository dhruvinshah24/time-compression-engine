"""Schema for Frame."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class FrameBase(BaseModel):
    pass

class FrameCreate(FrameBase):
    pass

class FrameResponse(FrameBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
