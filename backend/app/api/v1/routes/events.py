"""Events route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_events():
    return []

@router.get("/{id}")
async def get_event(id: str):
    return {"id": id}

@router.get("/{id}/explanation")
async def get_event_explanation(id: str):
    return {"id": id, "explanation": {}}
