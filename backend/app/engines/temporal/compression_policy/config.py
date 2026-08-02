"""
Configuration for Phase 9: Compression Policy.

The target_ratio is the primary dial. Everything else is a policy parameter
that can be tuned empirically.
"""
from dataclasses import dataclass


@dataclass
class CompressionConfig:
    """
    Policy parameters for keep/discard decisions.

    target_ratio:
        Fraction of events to retain (e.g. 0.30 = keep 30%).
        The actual ratio may vary slightly due to chain atomicity
        (we never split a COMPLETE chain mid-way).

    always_keep_complete:
        If True, all COMPLETE story arcs are kept regardless of ratio.
        This preserves full narratives at the cost of higher retention.
        Recommended for research demos.

    completeness_min_threshold:
        Segments with narrative_score below this are discarded first,
        regardless of importance. Used to clear low-quality noise.

    chain_atomicity:
        If True, events in the same story segment are kept or discarded
        as a unit (not individually). This prevents narrative fragmentation.
        Per mentor: "Entry → Walk → Pickup → Exit should survive or
        disappear as a unit."
    """
    target_ratio: float = 0.40             # keep 40% of events
    always_keep_complete: bool = True
    completeness_min_threshold: float = 0.20
    chain_atomicity: bool = True
