"""Analytics route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
async def get_stats():
    return {"total_videos": 0}
