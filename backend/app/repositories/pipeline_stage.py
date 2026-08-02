"""Repository for PipelineStage."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.pipeline_stage import PipelineStage
from app.schemas.pipeline_stage import PipelineStageCreate

class PipelineStageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
