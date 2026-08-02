"""Timeline route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/{video_id}")
async def get_timeline(video_id: str):
    return {"events": []}
