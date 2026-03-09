"""Job status + SSE streaming."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Job
from backend.schemas import JobStatus
from backend.services.job_manager import get_job, sse_generator

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatus)
def job_status(job_id: str, db: Session = Depends(get_db)):
    mem = get_job(job_id)
    if mem:
        return JobStatus(**mem)
    # Fallback to DB
    job = db.query(Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatus(
        id=job.id,
        dataset_id=job.dataset_id,
        status=job.status,
        current_step=job.current_step,
        percent=job.percent,
        message=job.message,
        error=job.error,
    )


@router.get("/{job_id}/events")
async def job_events(job_id: str):
    return StreamingResponse(
        sse_generator(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
