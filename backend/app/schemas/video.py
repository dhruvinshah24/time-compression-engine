"""Schema for Video."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class VideoBase(BaseModel):
    pass

class VideoCreate(VideoBase):
    pass

class VideoResponse(VideoBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
