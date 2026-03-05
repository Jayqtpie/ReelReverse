from ..database import SessionLocal
from ..services.maintenance.cleanup import run_retention_cleanup
from ..services.jobs import process_job
from .celery_app import celery_app


@celery_app.task(name="app.worker.tasks.process_job_task", autoretry_for=(Exception,), retry_backoff=True, max_retries=2)
def process_job_task(job_id: str):
    db = SessionLocal()
    try:
        process_job(db, job_id)
    finally:
        db.close()


def enqueue_process_job(job_id: str) -> None:
    process_job_task.delay(job_id)


@celery_app.task(name="app.worker.tasks.cleanup_task")
def cleanup_task():
    return run_retention_cleanup()
