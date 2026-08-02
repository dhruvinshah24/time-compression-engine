"""Schema for DetectedObject."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class DetectedObjectBase(BaseModel):
    pass

class DetectedObjectCreate(DetectedObjectBase):
    pass

class DetectedObjectResponse(DetectedObjectBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
