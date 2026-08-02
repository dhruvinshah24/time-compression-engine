"""Repository for SystemSetting."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.system_setting import SystemSetting
from app.schemas.system_setting import SystemSettingCreate

class SystemSettingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
