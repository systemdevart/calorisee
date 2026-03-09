"""In-memory job tracking + SSE streaming."""

import asyncio
import json
import logging
from datetime import datetime, timezone

from backend.models import Job, new_id, utcnow

logger = logging.getLogger(__name__)

# In-memory store: job_id -> dict with live progress
_jobs: dict[str, dict] = {}


def create_job(dataset_id: str, db) -> str:
    """Create a new job row and register in-memory tracker."""
    job_id = new_id()
    job = Job(id=job_id, dataset_id=dataset_id, status="pending", current_step="queued", percent=0, message="Waiting to start...")
    db.add(job)
    db.commit()
    _jobs[job_id] = {
        "id": job_id,
        "dataset_id": dataset_id,
        "status": "pending",
        "current_step": "queued",
        "percent": 0,
        "message": "Waiting to start...",
        "error": None,
    }
    return job_id


def update_job(job_id: str, db, *, status: str | None = None, current_step: str | None = None,
               percent: int | None = None, message: str | None = None, error: str | None = None):
    """Update both in-memory and DB job state."""
    mem = _jobs.get(job_id)
    if not mem:
        return
    if status is not None:
        mem["status"] = status
    if current_step is not None:
        mem["current_step"] = current_step
    if percent is not None:
        mem["percent"] = percent
    if message is not None:
        mem["message"] = message
    if error is not None:
        mem["error"] = error

    job = db.query(Job).get(job_id)
    if job:
        if status is not None:
            job.status = status
        if current_step is not None:
            job.current_step = current_step
        if percent is not None:
            job.percent = percent
        if message is not None:
            job.message = message
        if error is not None:
            job.error = error
        job.updated_at = utcnow()
        db.commit()


def get_job(job_id: str) -> dict | None:
    return _jobs.get(job_id)


async def sse_generator(job_id: str):
    """Yield SSE events until job completes or fails."""
    while True:
        mem = _jobs.get(job_id)
        if not mem:
            yield f"data: {json.dumps({'error': 'job not found'})}\n\n"
            return
        yield f"data: {json.dumps(mem)}\n\n"
        if mem["status"] in ("completed", "failed"):
            return
        await asyncio.sleep(1)
