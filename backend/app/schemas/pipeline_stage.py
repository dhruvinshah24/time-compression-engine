"""Schema for PipelineStage."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class PipelineStageBase(BaseModel):
    pass

class PipelineStageCreate(PipelineStageBase):
    pass

class PipelineStageResponse(PipelineStageBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
