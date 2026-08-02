"""Summary route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/{video_id}")
async def get_summary(video_id: str):
    return {"summary": "", "stats": {}}
