"""Pipeline context."""
from dataclasses import dataclass, field
from typing import Any
from app.pipeline.result import StageResult

@dataclass
class PipelineContext:
    """Context passed through the pipeline."""
    job_id: str
    video_id: str
    video_path: str
    output_dir: str
    settings: dict[str, Any]
    stage_results: dict[str, StageResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    logger: Any = None
