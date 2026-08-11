"""Main API router."""
from fastapi import APIRouter
from app.api.v1.routes import (
    upload, videos, jobs, events, event_graph,
    timeline, summary, analytics, settings, models_registry, health, debug
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(event_graph.router, prefix="/event-graph", tags=["event_graph"])
api_router.include_router(timeline.router, prefix="/timeline", tags=["timeline"])
api_router.include_router(summary.router, prefix="/summary", tags=["summary"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(models_registry.router, prefix="/models", tags=["models"])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
