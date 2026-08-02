"""Repository for EventNode."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.event_node import EventNode
from app.schemas.event_node import EventNodeCreate

class EventNodeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
