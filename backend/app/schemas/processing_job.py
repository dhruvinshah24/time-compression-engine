"""Schema for ProcessingJob."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class ProcessingJobBase(BaseModel):
    pass

class ProcessingJobCreate(ProcessingJobBase):
    pass

class ProcessingJobResponse(ProcessingJobBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
