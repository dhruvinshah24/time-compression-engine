"""Analytics route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_analytics_summary():
    """Root analytics endpoint — returns aggregate statistics."""
    return {"total_videos": 0, "total_events": 0, "avg_compression_ratio": 0.0}

@router.get("/stats")
async def get_stats():
    return {"total_videos": 0}
