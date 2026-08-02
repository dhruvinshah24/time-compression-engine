"""Repository for SystemLog."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_log import SystemLog
from app.schemas.system_log import SystemLogCreate

class SystemLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
