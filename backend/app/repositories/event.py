"""Repository for Event."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event import Event
from app.schemas.event import EventCreate

class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
