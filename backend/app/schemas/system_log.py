"""Schema for SystemLog."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class SystemLogBase(BaseModel):
    pass

class SystemLogCreate(SystemLogBase):
    pass

class SystemLogResponse(SystemLogBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
