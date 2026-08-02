"""Event graph route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/{video_id}")
async def get_event_graph(video_id: str):
    return {"nodes": [], "edges": []}
