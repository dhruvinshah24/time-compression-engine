"""Repository for Frame."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.frame import Frame
from app.schemas.frame import FrameCreate

class FrameRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
