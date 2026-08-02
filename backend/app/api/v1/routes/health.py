"""Health check route."""
from fastapi import APIRouter
from app.engines.perception.frame_extractor.extractor import FrameExtractor

router = APIRouter()

@router.get("/health")
async def health_check():
    extractor = FrameExtractor()
    return {
        "status": "ok",
        "engines": [extractor.get_metrics().name]
    }
