"""
Logging configuration — Time Compression Engine.

Phase 1 stub. Configures Python's standard logging with a sensible format.
Replace with structlog integration (already in requirements.txt) in Phase 3.
"""

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """
    Configure application-wide logging.

    Args:
        level: Logging level string ("DEBUG", "INFO", "WARNING", "ERROR").

    Note: Phase 1 uses stdlib logging. Phase 3 will migrate to structlog
    for structured JSON output compatible with log aggregation systems.
    """
    logging.basicConfig(
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
