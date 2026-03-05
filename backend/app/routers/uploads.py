from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ..config import settings
from ..deps import get_current_user
from ..models import User
from ..schemas import UploadPresignRequest, UploadPresignResponse
from ..services.media_pipeline import media_root, resolve_upload_path

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


@router.post("/presign", response_model=UploadPresignResponse)
def create_presigned_upload(
    payload: UploadPresignRequest,
    user: User = Depends(get_current_user),
):
    safe_name = Path(payload.filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="invalid_filename")
    file_key = f"{user.id}/{safe_name}"
    return UploadPresignResponse(
        file_key=file_key,
        upload_url=f"/v1/uploads/{file_key}",
        max_upload_mb=settings.max_upload_mb,
    )


@router.put("/{file_key:path}")
async def upload_blob(
    file_key: str,
    request: Request,
    user: User = Depends(get_current_user),
):
    blob = await request.body()
    if not file_key.startswith(f"{user.id}/"):
        raise HTTPException(status_code=403, detail="forbidden_upload_key")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(blob) > max_bytes:
        raise HTTPException(status_code=413, detail="too_large")

    try:
        path = resolve_upload_path(file_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid_file_key") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return Response(status_code=204)


@router.get("/health")
def upload_health(user: User = Depends(get_current_user)):
    root = media_root()
    return {"ok": True, "user_id": user.id, "media_dir": str(root)}
