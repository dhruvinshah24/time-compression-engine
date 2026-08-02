"""
Storage utility — Time Compression Engine, Phase 2.

Manages all file I/O for uploaded videos and pipeline outputs.
The interface is designed to be local-first but S3-ready: swapping the
backend in Phase 14 requires only changing this module.

Directory conventions (all relative to STORAGE_LOCAL_PATH):
    uploads/{job_id}/original.{ext}          — uploaded source file
    outputs/frames/{job_id}/chunk_*/          — extracted frames
    outputs/thumbnails/{job_id}/{event_id}.jpg
    outputs/clips/{job_id}/{event_id}.mp4
    outputs/highlight_videos/{job_id}/highlight.mp4
    outputs/timelines/{job_id}/timeline.json
    outputs/reports/{job_id}/report.json
"""

import hashlib
import logging
import shutil
from pathlib import Path
from typing import BinaryIO

logger = logging.getLogger(__name__)

# Default storage root — overridden by STORAGE_LOCAL_PATH env var
_DEFAULT_STORAGE_ROOT = Path(__file__).parent.parent.parent.parent.parent / "outputs"


def get_storage_root() -> Path:
    """Return the configured storage root directory."""
    import os
    root = os.environ.get("STORAGE_LOCAL_PATH")
    if root:
        return Path(root)
    return _DEFAULT_STORAGE_ROOT


def get_upload_path(job_id: str, original_filename: str) -> Path:
    """
    Return the canonical storage path for an uploaded video.

    The original extension is preserved. The filename is normalized to
    'original.{ext}' so downstream code never needs to know the original name.
    """
    ext = Path(original_filename).suffix.lower()
    upload_dir = get_storage_root().parent / "storage" / "uploads" / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir / f"original{ext}"


def get_frames_dir(job_id: str) -> Path:
    """Return the directory where extracted frames are stored for a job."""
    frames_dir = get_storage_root() / "frames" / job_id
    frames_dir.mkdir(parents=True, exist_ok=True)
    return frames_dir


def get_thumbnails_dir(job_id: str) -> Path:
    """Return the directory for event thumbnails."""
    d = get_storage_root() / "thumbnails" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_clips_dir(job_id: str) -> Path:
    """Return the directory for individual event video clips."""
    d = get_storage_root() / "clips" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_highlight_video_path(job_id: str) -> Path:
    """Return the path for the final compressed highlight video."""
    d = get_storage_root() / "highlight_videos" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "highlight.mp4"


def get_timeline_path(job_id: str) -> Path:
    """Return the path for the exported event timeline JSON."""
    d = get_storage_root() / "timelines" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "timeline.json"


def get_report_path(job_id: str) -> Path:
    """Return the path for the processing report JSON."""
    d = get_storage_root() / "reports" / job_id
    d.mkdir(parents=True, exist_ok=True)
    return d / "report.json"


async def save_upload(
    file_obj: BinaryIO,
    job_id: str,
    original_filename: str,
    chunk_size: int = 8 * 1024 * 1024,  # 8 MB chunks
) -> tuple[Path, int, str]:
    """
    Save an uploaded file to disk in chunks (memory-efficient).

    Args:
        file_obj:          File-like object (e.g., from FastAPI UploadFile).
        job_id:            Processing job ID.
        original_filename: Original filename for extension detection.
        chunk_size:        Read/write chunk size in bytes.

    Returns:
        (saved_path, file_size_bytes, sha256_hex)

    The SHA-256 hash is computed during streaming and can be used for
    deduplication or integrity verification.
    """
    dest = get_upload_path(job_id, original_filename)
    hasher = hashlib.sha256()
    total_bytes = 0

    logger.info("Saving upload for job %s → %s", job_id, dest)

    with open(dest, "wb") as out:
        while True:
            chunk = await file_obj.read(chunk_size) if hasattr(file_obj, "read") else file_obj.read(chunk_size)
            if not chunk:
                break
            out.write(chunk)
            hasher.update(chunk)
            total_bytes += len(chunk)

    sha256 = hasher.hexdigest()
    logger.info(
        "Saved %d bytes for job %s (SHA-256: %s...)",
        total_bytes, job_id, sha256[:16]
    )
    return dest, total_bytes, sha256


def delete_job_files(job_id: str) -> dict[str, int]:
    """
    Delete all stored files for a processing job.

    Returns a dict with counts of deleted files per category.
    """
    root = get_storage_root()
    storage_root = root.parent / "storage"
    deleted: dict[str, int] = {}

    for category, base in [
        ("uploads", storage_root / "uploads" / job_id),
        ("frames", root / "frames" / job_id),
        ("thumbnails", root / "thumbnails" / job_id),
        ("clips", root / "clips" / job_id),
        ("highlight_videos", root / "highlight_videos" / job_id),
        ("timelines", root / "timelines" / job_id),
        ("reports", root / "reports" / job_id),
    ]:
        if base.exists():
            count = sum(1 for _ in base.rglob("*") if _.is_file())
            shutil.rmtree(base, ignore_errors=True)
            deleted[category] = count
            logger.info("Deleted %d files from %s for job %s", count, category, job_id)

    return deleted


def get_storage_stats() -> dict[str, int | float]:
    """Return storage usage statistics across all jobs."""
    root = get_storage_root()
    total_bytes = sum(
        f.stat().st_size
        for f in root.rglob("*")
        if f.is_file()
    )
    return {
        "total_bytes": total_bytes,
        "total_gb": round(total_bytes / (1024 ** 3), 3),
    }
