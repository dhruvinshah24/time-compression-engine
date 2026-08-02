"""Repository for ProcessingJob."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.processing_job import ProcessingJob
from app.schemas.processing_job import ProcessingJobCreate

class ProcessingJobRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def get(self, id: str):
        pass
