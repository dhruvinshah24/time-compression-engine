"""Base classes for AI engines."""
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod
from app.pipeline.context import PipelineContext
from app.pipeline.result import StageResult

class ModuleHealth(Enum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    STUB = "stub"

@dataclass 
class ModuleMetrics:
    name: str
    version: str
    engine: str
    calls_total: int = 0
    avg_duration_ms: float = 0.0
    last_health: ModuleHealth = ModuleHealth.STUB

class IntelligenceModule(ABC):
    name: str
    version: str = "0.1.0"
    engine: str
    
    @abstractmethod
    async def process(self, context: PipelineContext) -> StageResult:
        pass
    
    @abstractmethod
    def health_check(self) -> ModuleHealth:
        pass
    
    @abstractmethod
    def get_metrics(self) -> ModuleMetrics:
        pass
