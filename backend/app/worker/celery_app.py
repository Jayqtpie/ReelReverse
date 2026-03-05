from celery import Celery

from ..config import settings

celery_app = Celery("reelrev_worker", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.worker.tasks.process_job_task": {"queue": "analysis_jobs"}}
