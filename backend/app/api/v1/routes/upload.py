"""Upload route."""
from fastapi import APIRouter

router = APIRouter()

@router.post("/")
async def upload_video():
    return {"status": "uploaded"}
