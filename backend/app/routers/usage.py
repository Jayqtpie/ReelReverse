from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import UsageResponse
from ..services.jobs import usage_snapshot

router = APIRouter(prefix="/v1/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
def get_usage(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return UsageResponse(**usage_snapshot(db, user))
