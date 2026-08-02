"""Repository for DetectedObject."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.detected_object import DetectedObject
from app.schemas.detected_object import DetectedObjectCreate

class DetectedObjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
