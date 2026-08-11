"""Videos route — reads from InMemoryVideoRepository."""
import logging
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from app.repositories.inmemory import get_video_repo, get_job_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def list_videos():
    repo = get_video_repo()
    videos = await repo.list()
    # Enrich with latest job status
    job_repo = get_job_repo()
    result = []
    for v in videos:
        jobs = await job_repo.get_by_video(v["id"])
        latest_job = jobs[0] if jobs else None
        result.append({
            **v,
            "latest_job_status": latest_job["status"] if latest_job else None,
            "latest_job_id": latest_job["id"] if latest_job else None,
        })
    return result


@router.get("/{video_id}")
async def get_video(video_id: str):
    repo = get_video_repo()
    video = await repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return video


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    repo = get_video_repo()
    deleted = await repo.delete(video_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return {"status": "deleted", "video_id": video_id}


@router.get("/{video_id}/stream")
async def stream_video(video_id: str, request: Request):
    """
    Stream the original uploaded video for the HTML5 player.
    Supports HTTP range requests so seek works correctly.
    """
    repo = get_video_repo()
    video = await repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    video_path = video.get("file_path") or video.get("path")
    if not video_path or not Path(video_path).exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("range")

    # Determine MIME type
    suffix = Path(video_path).suffix.lower()
    mime = {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/x-msvideo",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }.get(suffix, "video/mp4")

    if range_header:
        # Parse range: "bytes=start-end"
        try:
            range_val = range_header.replace("bytes=", "")
            start_str, end_str = range_val.split("-")
            start = int(start_str)
            end = int(end_str) if end_str else file_size - 1
        except Exception:
            start, end = 0, file_size - 1

        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iter_file():
            with open(video_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type=mime,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            },
        )

    # No range — serve full file
    return FileResponse(video_path, media_type=mime, headers={"Accept-Ranges": "bytes"})


@router.get("/{video_id}/frames")
async def get_event_frames(video_id: str):
    """Return paths to extracted frames for this video (for thumbnail previews)."""
    repo = get_video_repo()
    video = await repo.get(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    frames_dir = video.get("frames_dir")
    if not frames_dir or not Path(frames_dir).exists():
        return {"frames": [], "frames_dir": None}
    frames = sorted(Path(frames_dir).glob("frame_*.jpg"))
    return {
        "frames_dir": frames_dir,
        "total_frames": len(frames),
        "sample_frames": [str(f) for f in frames[::max(1, len(frames)//20)][:20]],
    }
