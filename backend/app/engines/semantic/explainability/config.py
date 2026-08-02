"""Configuration for the Explainability module."""
from dataclasses import dataclass

@dataclass
class ExplainabilityConfig:
    enabled: bool = True
    max_chain_length: int = 10
    include_signal_weights: bool = True
    include_rejected_events: bool = False
