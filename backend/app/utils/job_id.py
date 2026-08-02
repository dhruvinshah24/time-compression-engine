"""
Job ID generation utility for Time Compression Engine.

Every processing job is assigned a human-readable, unique identifier
in the format: JOB-{YYYYMMDD}-{SEQUENCE:04d}

Examples:
    JOB-20260730-0001
    JOB-20260730-0002
    JOB-20260801-0001

This identifier is used consistently across:
- Pipeline logs
- Database records (processing_jobs.job_display_id)
- Exported reports
- Generated video clips and thumbnails
- Output directory structure

Using a human-readable ID instead of a raw UUID makes debugging,
log searching, and cross-referencing outputs significantly easier
once multiple videos are being processed concurrently.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

# Sequence counter file — persisted locally to maintain monotonic ordering
# In production, this should be stored in the database or Redis
_COUNTER_FILE = Path(__file__).parent.parent.parent / "outputs" / "logs" / ".job_counter"


def _read_counter(date_str: str) -> int:
    """Read the current sequence counter for today's date."""
    if not _COUNTER_FILE.exists():
        return 0
    try:
        content = _COUNTER_FILE.read_text().strip()
        stored_date, stored_count = content.split(":")
        if stored_date == date_str:
            return int(stored_count)
    except (ValueError, FileNotFoundError):
        pass
    return 0


def _write_counter(date_str: str, count: int) -> None:
    """Persist the sequence counter."""
    _COUNTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    _COUNTER_FILE.write_text(f"{date_str}:{count}")


def generate_job_id() -> str:
    """
    Generate a unique, human-readable processing job identifier.

    Format: JOB-{YYYYMMDD}-{SEQUENCE:04d}

    The sequence resets daily. Thread safety is not guaranteed for
    high-concurrency scenarios — use database sequences in production.

    Returns:
        str: e.g. "JOB-20260730-0001"
    """
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    current = _read_counter(date_str)
    next_seq = current + 1
    _write_counter(date_str, next_seq)
    return f"JOB-{date_str}-{next_seq:04d}"


def parse_job_id(job_id: str) -> dict:
    """
    Parse a job ID into its constituent parts.

    Args:
        job_id: e.g. "JOB-20260730-0001"

    Returns:
        {"date": "20260730", "sequence": 1, "valid": True}
    """
    pattern = r"^JOB-(\d{8})-(\d{4})$"
    match = re.match(pattern, job_id)
    if not match:
        return {"valid": False}
    return {
        "valid": True,
        "date": match.group(1),
        "sequence": int(match.group(2)),
    }


def get_output_dir(job_id: str, output_type: str) -> Path:
    """
    Get the standard output directory for a job and output type.

    Args:
        job_id: e.g. "JOB-20260730-0001"
        output_type: One of: highlight_videos, timelines, reports,
                     logs, thumbnails, clips

    Returns:
        Path to the output directory (created if not exists)
    """
    base = Path(__file__).parent.parent.parent / "outputs" / output_type / job_id
    base.mkdir(parents=True, exist_ok=True)
    return base
