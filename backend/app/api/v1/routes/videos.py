"""Videos route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_videos():
    return []

@router.get("/{id}")
async def get_video(id: str):
    return {"id": id}

@router.delete("/{id}")
async def delete_video(id: str):
    return {"status": "deleted"}
