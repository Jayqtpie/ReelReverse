from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..enums import JobState
from ..models import AnalysisJob, User
from ..schemas import JobCreateRequest, JobCreateResponse, JobStatusResponse
from ..services.jobs import create_job, process_job
from ..worker.tasks import enqueue_process_job

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobCreateResponse)
def submit_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = create_job(db, user, payload)
    if job.state != JobState.DONE.value:
        _dispatch_job(job.id, db)
    return JobCreateResponse(job_id=job.id, state=JobState(job.state), eta_seconds=120)


def _dispatch_job(job_id: str, db: Session) -> None:
    if settings.queue_mode == "inline":
        process_job(db, job_id)
        return
    try:
        enqueue_process_job(job_id)
    except Exception:
        # Fallback keeps local/dev flow usable when Redis/Celery is unavailable.
        process_job(db, job_id)


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    return JobStatusResponse(
        job_id=job.id,
        state=JobState(job.state),
        progress=job.progress,
        stage=job.stage,
        error_code=job.error_code,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
