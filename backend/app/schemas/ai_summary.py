"""Schema for AiSummary."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class AiSummaryBase(BaseModel):
    pass

class AiSummaryCreate(AiSummaryBase):
    pass

class AiSummaryResponse(AiSummaryBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
