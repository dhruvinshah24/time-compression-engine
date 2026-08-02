"""
Stage metrics auto-save utility — Time Compression Engine.

Every pipeline stage calls save_stage_metrics() so that performance data
is automatically persisted without requiring extra code in each stage.

These metrics files are the raw data for the phase reports and will
eventually feed into performance visualization charts.

Output path: outputs/logs/{job_id}/{stage_name}_metrics.json
"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def save_stage_metrics(job_id: str, stage_name: str, metrics: dict) -> Path | None:
    """
    Save stage execution metrics to a JSON file.

    Args:
        job_id:     Processing job identifier (e.g., JOB-20260730-0001)
        stage_name: Pipeline stage name (e.g., "s03_scene_detect")
        metrics:    Dict of metric values to record

    Returns:
        Path to the saved file, or None if saving failed (non-fatal).

    The saved format includes:
    {
        "job_id": "JOB-20260730-0001",
        "stage": "s03_scene_detect",
        "timestamp_utc": "2026-07-30T18:00:00",
        "metrics": { ... stage-specific metrics ... }
    }
    """
    try:
        from app.utils.storage import get_storage_root
        log_dir = get_storage_root() / "logs" / job_id
        log_dir.mkdir(parents=True, exist_ok=True)
        output_path = log_dir / f"{stage_name}_metrics.json"

        payload = {
            "job_id": job_id,
            "stage": stage_name,
            "timestamp_utc": _utc_now(),
            "metrics": metrics,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

        logger.debug("Stage metrics saved: %s", output_path)
        return output_path

    except Exception as exc:
        # Metrics saving must never fail the pipeline
        logger.warning("Failed to save stage metrics for %s/%s: %s", job_id, stage_name, exc)
        return None


def load_stage_metrics(job_id: str, stage_name: str) -> dict | None:
    """
    Load previously saved stage metrics.

    Returns None if the metrics file doesn't exist.
    """
    try:
        from app.utils.storage import get_storage_root
        log_dir = get_storage_root() / "logs" / job_id
        path = log_dir / f"{stage_name}_metrics.json"

        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Failed to load stage metrics for %s/%s: %s", job_id, stage_name, exc)
        return None


def load_all_job_metrics(job_id: str) -> dict[str, dict]:
    """
    Load all stage metrics for a job, keyed by stage name.

    Useful for building the final performance report.
    """
    result: dict[str, dict] = {}
    try:
        from app.utils.storage import get_storage_root
        log_dir = get_storage_root() / "logs" / job_id

        if not log_dir.exists():
            return result

        for metrics_file in sorted(log_dir.glob("*_metrics.json")):
            try:
                with open(metrics_file, encoding="utf-8") as f:
                    data = json.load(f)
                stage = data.get("stage", metrics_file.stem.replace("_metrics", ""))
                result[stage] = data
            except Exception:
                pass

    except Exception as exc:
        logger.warning("Failed to load job metrics for %s: %s", job_id, exc)

    return result


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
