"""Jobs route — reads from InMemoryJobRepository."""
import logging
from fastapi import APIRouter, HTTPException
from app.repositories.inmemory import get_job_repo

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def list_jobs():
    repo = get_job_repo()
    return await repo.list()


@router.get("/{job_id}")
async def get_job(job_id: str):
    repo = get_job_repo()
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    repo = get_job_repo()
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    updated = await repo.update(job_id, {"status": "cancelled"})
    return {"status": "cancelled", "job_id": job_id}
