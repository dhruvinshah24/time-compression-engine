"""Schema for SystemSetting."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class SystemSettingBase(BaseModel):
    pass

class SystemSettingCreate(SystemSettingBase):
    pass

class SystemSettingResponse(SystemSettingBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
