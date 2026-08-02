"""Configuration for the Summary Engine module."""
from dataclasses import dataclass

@dataclass
class SummaryEngineConfig:
    max_summary_length: int = 500
    include_event_list: bool = True
    include_compression_stats: bool = True
    model_backend: str = "template"  # Phase 11+: "openai", "local_llm"
