from fastapi import APIRouter, Depends

from ..config import settings
from ..deps import get_current_user
from ..models import User
from ..services.maintenance.cleanup import run_retention_cleanup
from ..worker.tasks import cleanup_task

router = APIRouter(prefix="/v1/maintenance", tags=["maintenance"])


@router.post("/cleanup")
def cleanup_now(user: User = Depends(get_current_user)):
    if settings.queue_mode == "celery":
        task = cleanup_task.delay()
        return {"queued": True, "task_id": task.id}
    result = run_retention_cleanup()
    return {"queued": False, "result": result}
