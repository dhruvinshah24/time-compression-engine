"""Settings route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_settings():
    return []

@router.put("/{key}")
async def update_setting(key: str):
    return {"key": key, "updated": True}
