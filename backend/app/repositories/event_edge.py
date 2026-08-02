"""Repository for EventEdge."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event_edge import EventEdge
from app.schemas.event_edge import EventEdgeCreate

class EventEdgeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
