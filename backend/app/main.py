"""Main FastAPI application."""
import os
import sys
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

# ── PATH bootstrap: find ffprobe even if installed after this process started ──
# Windows WinGet installs update the registry PATH but not the current process.
# We patch os.environ["PATH"] at startup so shutil.which() works in-process.
def _patch_ffmpeg_path() -> None:
    if shutil.which("ffprobe"):
        return  # already found

    candidates = [
        # WinGet default per-user install location
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        # Common manual install locations
        Path("C:/ffmpeg/bin"),
        Path("C:/Program Files/ffmpeg/bin"),
        Path(os.environ.get("ProgramFiles", "")) / "ffmpeg" / "bin",
    ]

    # Walk WinGet packages tree looking for ffprobe.exe
    winget_base = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if winget_base.exists():
        for p in winget_base.rglob("ffprobe.exe"):
            candidates.append(p.parent)
            break

    for candidate in candidates:
        if candidate.exists() and (candidate / "ffprobe.exe").exists():
            current = os.environ.get("PATH", "")
            os.environ["PATH"] = str(candidate) + os.pathsep + current
            print(f"[TCE] Patched PATH: added {candidate}", file=sys.stderr)
            return

_patch_ffmpeg_path()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Time Compression Engine API",
    description="Research-grade video event summarization system",
    version="1.0.1",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    redirect_slashes=True,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)
