"""Jobs route."""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def list_jobs():
    return []

@router.get("/{id}")
async def get_job(id: str):
    return {"id": id, "stages": []}

@router.post("/{id}/cancel")
async def cancel_job(id: str):
    return {"status": "cancelled"}
