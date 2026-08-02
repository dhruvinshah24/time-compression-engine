"""Repository for AiSummary."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ai_summary import AiSummary
from app.schemas.ai_summary import AiSummaryCreate

class AiSummaryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
