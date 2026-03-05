from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..enums import JobState
from ..models import AnalysisJob, AnalysisReport, User
from ..schemas import (
    ArtifactsResponse,
    ExportRequest,
    ExportResponse,
    ReportListItem,
    ReportListResponse,
    ReportResponse,
    TimelineResponse,
)
from ..services.report_export import create_export_artifact, verify_export_token

router = APIRouter(prefix="/v1/reports", tags=["reports"])


@router.get("/{job_id}", response_model=ReportResponse)
def get_report(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.state != JobState.DONE.value:
        raise HTTPException(status_code=404, detail="report_not_ready")
    report = db.query(AnalysisReport).filter(AnalysisReport.job_id == job.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="report_not_ready")
    data = report.report_json
    artifacts = _artifact_snapshot(job)
    return ReportResponse(
        job_id=job.id,
        hook_analysis=data["hook_analysis"],
        pacing_timeline=data["pacing_timeline"],
        caption_formula=data["caption_formula"],
        remake_template=data["remake_template"],
        artifacts=artifacts,
        confidence=report.confidence,
        generated_at=report.created_at,
    )


@router.get("/{job_id}/artifacts", response_model=ArtifactsResponse)
def get_artifacts(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.state != JobState.DONE.value:
        raise HTTPException(status_code=404, detail="artifacts_not_ready")
    snapshot = _artifact_snapshot(job)
    return ArtifactsResponse(
        job_id=job.id,
        transcript={
            "source": snapshot["transcript_source"],
            "quality": snapshot["transcript_quality"],
            "word_count": snapshot["transcript_word_count"],
        },
        features={
            "source_mode": snapshot["feature_source_mode"],
            "scene_quality": snapshot["scene_quality"],
            "cut_frequency": snapshot["cut_frequency"],
            "audio_spike": snapshot["audio_spike"],
        },
    )


@router.get("/{job_id}/timeline", response_model=TimelineResponse)
def get_timeline(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    if job.state != JobState.DONE.value:
        raise HTTPException(status_code=404, detail="timeline_not_ready")
    feature = job.feature_artifact
    timeline = feature.timeline_json if feature and isinstance(feature.timeline_json, list) else []
    return TimelineResponse(job_id=job.id, timeline=timeline)


@router.get("", response_model=ReportListResponse)
def list_reports(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    jobs = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.user_id == user.id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(min(max(limit, 1), 100))
        .all()
    )
    items: list[ReportListItem] = []
    for job in jobs:
        report = db.query(AnalysisReport).filter(AnalysisReport.job_id == job.id).first()
        items.append(
            ReportListItem(
                job_id=job.id,
                state=JobState(job.state),
                created_at=job.created_at,
                confidence=report.confidence if report else None,
            )
        )
    return ReportListResponse(items=items, next_cursor=None)


@router.post("/{job_id}/export", response_model=ExportResponse)
def export_report(
    job_id: str,
    payload: ExportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job_not_found")
    report = db.query(AnalysisReport).filter(AnalysisReport.job_id == job.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="report_not_ready")
    export_data = create_export_artifact(
        job_id=job.id,
        user_id=user.id,
        fmt=payload.format,
        report_json=report.report_json,
    )
    return ExportResponse(download_url=export_data["download_url"], expires_at=export_data["expires_at"])


@router.get("/download/{token}")
def download_export(
    token: str,
    user: User = Depends(get_current_user),
):
    try:
        token_data = verify_export_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if token_data["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="forbidden_export_access")

    fmt = token_data["format"]
    artifact = Path(settings.export_dir) / f"{token_data['job_id']}.{fmt}"
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="export_not_found")
    media_type = "application/json" if fmt == "json" else "application/pdf"
    filename = artifact.name
    return FileResponse(path=artifact, media_type=media_type, filename=filename)


def _artifact_snapshot(job: AnalysisJob) -> dict:
    transcript = job.transcript_artifact
    feature = job.feature_artifact
    return {
        "transcript_source": transcript.source if transcript else "unknown",
        "transcript_quality": float(transcript.quality) if transcript else 0.0,
        "transcript_word_count": int(transcript.word_count) if transcript else 0,
        "feature_source_mode": feature.source_mode if feature else "unknown",
        "scene_quality": float(feature.scene_quality) if feature else 0.0,
        "cut_frequency": float(feature.cut_frequency) if feature else 0.0,
        "audio_spike": float(feature.audio_spike) if feature else 0.0,
    }
