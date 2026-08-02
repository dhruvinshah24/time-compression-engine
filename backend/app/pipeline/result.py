"""Pipeline stage result definition."""
from dataclasses import dataclass, field
from typing import Any

@dataclass
class StageResult:
    """Result of a pipeline stage."""
    success: bool
    stage_name: str
    duration_ms: int
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stage_name": self.stage_name,
            "duration_ms": self.duration_ms,
            "warnings": self.warnings,
            "errors": self.errors,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "logs": self.logs
        }
