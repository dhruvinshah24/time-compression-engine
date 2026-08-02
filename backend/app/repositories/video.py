"""Repository for Video."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.video import Video
from app.schemas.video import VideoCreate

class VideoRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
