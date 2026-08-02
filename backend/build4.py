import os
from pathlib import Path

base = Path(r"C:\Users\dhruv\.gemini\antigravity\scratch\time-compression-engine\backend")

def write_file(path_str, content):
    p = base / path_str
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")

# API Routes
routes = ["upload", "videos", "jobs", "events", "event_graph", "timeline", "summary", "analytics", "settings", "models_registry", "health"]

write_file("app/api/__init__.py", "")
write_file("app/api/v1/__init__.py", "")
write_file("app/api/v1/routes/__init__.py", "")

for r in routes:
    write_file(f"app/api/v1/routes/{r}.py", f"""
\"\"\"Route {r}.\"\"\"
from fastapi import APIRouter

router = APIRouter()
""")

# Custom implementations for routes
write_file("app/api/v1/routes/health.py", """
\"\"\"Health check route.\"\"\"
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
""")

write_file("app/api/v1/routes/videos.py", """
\"\"\"Videos route.\"\"\"
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
""")

write_file("app/api/v1/routes/jobs.py", """
\"\"\"Jobs route.\"\"\"
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
""")

write_file("app/api/v1/routes/events.py", """
\"\"\"Events route.\"\"\"
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
""")

write_file("app/api/v1/routes/event_graph.py", """
\"\"\"Event graph route.\"\"\"
from fastapi import APIRouter

router = APIRouter()

@router.get("/{video_id}")
async def get_event_graph(video_id: str):
    return {"nodes": [], "edges": []}
""")

write_file("app/api/v1/routes/timeline.py", """
\"\"\"Timeline route.\"\"\"
from fastapi import APIRouter

router = APIRouter()

@router.get("/{video_id}")
async def get_timeline(video_id: str):
    return {"events": []}
""")

write_file("app/api/v1/routes/summary.py", """
\"\"\"Summary route.\"\"\"
from fastapi import APIRouter

router = APIRouter()

@router.get("/{video_id}")
async def get_summary(video_id: str):
    return {"summary": "", "stats": {}}
""")

write_file("app/api/v1/routes/analytics.py", """
\"\"\"Analytics route.\"\"\"
from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
async def get_stats():
    return {"total_videos": 0}
""")

write_file("app/api/v1/routes/settings.py", """
\"\"\"Settings route.\"\"\"
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_settings():
    return []

@router.put("/{key}")
async def update_setting(key: str):
    return {"key": key, "updated": True}
""")

write_file("app/api/v1/routes/models_registry.py", """
\"\"\"Models registry route.\"\"\"
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_models():
    return []
""")

write_file("app/api/v1/routes/upload.py", """
\"\"\"Upload route.\"\"\"
from fastapi import APIRouter

router = APIRouter()

@router.post("/")
async def upload_video():
    return {"status": "uploaded"}
""")


# Router aggregator
write_file("app/api/v1/router.py", """
\"\"\"Main API router.\"\"\"
from fastapi import APIRouter
from app.api.v1.routes import (
    upload, videos, jobs, events, event_graph,
    timeline, summary, analytics, settings, models_registry, health
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
""")

# App Main
write_file("app/main.py", """
\"\"\"Main FastAPI application.\"\"\"
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown

app = FastAPI(
    title="Time Compression Engine API",
    description="Research-grade video event summarization system",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
""")


# Alembic setup and Tests
write_file("alembic/env.py", """
\"\"\"Alembic env.\"\"\"
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    connectable = create_async_engine(settings.DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

if context.is_offline_mode():
    pass
else:
    asyncio.run(run_migrations_online())
""")

write_file("alembic/script.py.mako", '\"\"\"Mako template.\"\"\"')

write_file("alembic/versions/0001_initial_schema.py", """
\"\"\"Initial schema.\"\"\"
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False)
    )
    # Add other tables as needed for complete migration
    pass

def downgrade():
    op.drop_table('users')
    pass
""")

write_file("tests/__init__.py", "")
write_file("tests/conftest.py", '\"\"\"Test fixtures.\"\"\"')
write_file("tests/unit/__init__.py", "")
write_file("tests/unit/test_pipeline_result.py", '\"\"\"Test pipeline result.\"\"\"')
write_file("tests/unit/test_engines_base.py", '\"\"\"Test engines base.\"\"\"')
write_file("tests/unit/test_orchestrator.py", '\"\"\"Test orchestrator.\"\"\"')
write_file("tests/integration/__init__.py", "")
write_file("tests/integration/test_health.py", '\"\"\"Test health route.\"\"\"')

print("Build 4 complete")
