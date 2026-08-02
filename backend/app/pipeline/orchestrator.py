"""Pipeline orchestrator."""
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

class PipelineOrchestrator:
    async def run_pipeline(self, context: PipelineContext) -> bool:
        # Stub implementation
        return True
