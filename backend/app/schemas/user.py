"""Schema for User."""
from pydantic import BaseModel
from typing import Optional, Any
import uuid

class UserBase(BaseModel):
    pass

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: uuid.UUID
    class Config:
        from_attributes = True
