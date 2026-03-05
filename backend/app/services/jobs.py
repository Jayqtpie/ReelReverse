from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..enums import JobState, SourceType
from ..models import AnalysisJob, AnalysisReport, FeatureArtifact, TranscriptArtifact, User
from ..schemas import JobCreateRequest
from .analysis_adapters import (
    estimate_audio_spike_ffmpeg,
    estimate_scene_rate_ffmpeg,
    load_transcript_sidecar,
    transcribe_with_openai,
    transcript_meta_from_text,
)
from .analysis_engine import build_report
from .media_pipeline import ffprobe_media, file_sha256, resolve_upload_path

YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "youtu.be"}


def _media_hash(source_type: SourceType, source_url: str | None, file_key: str | None) -> str:
    seed = f"{source_type}:{source_url or ''}:{file_key or ''}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _validate_url(source_url: str) -> None:
    domain = urlparse(source_url).netloc.lower()
    if domain not in YOUTUBE_DOMAINS:
        raise HTTPException(status_code=400, detail="invalid_source")


def _validate_quota(db: Session, user: User) -> None:
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    used = db.query(AnalysisJob).filter(AnalysisJob.user_id == user.id, AnalysisJob.created_at >= day_start).count()
    if used >= settings.free_jobs_per_day:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="quota_exceeded")


def create_job(db: Session, user: User, payload: JobCreateRequest) -> AnalysisJob:
    _validate_quota(db, user)
    if payload.source_type == SourceType.URL:
        _validate_url(str(payload.source_url))

    if payload.duration_sec and payload.duration_sec > settings.max_duration_sec:
        raise HTTPException(status_code=400, detail="duration_exceeds_limit")

    media_hash = _derive_media_hash(payload)
    existing = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.user_id == user.id, AnalysisJob.media_hash == media_hash)
        .first()
    )
    if existing:
        return existing

    job = AnalysisJob(
        user_id=user.id,
        source_type=payload.source_type.value,
        source_url=str(payload.source_url) if payload.source_url else None,
        file_key=payload.file_key,
        media_hash=media_hash,
        state=JobState.QUEUED.value,
        stage=JobState.QUEUED.value,
        progress=0,
        confirm_rights=payload.confirm_rights,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_job(db: Session, job_id: str) -> None:
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        return
    try:
        _set_stage(db, job, JobState.DOWNLOADING.value, 15)
        ingest_meta = _run_ingest_stage(job)

        _set_stage(db, job, JobState.PREPROCESSING.value, 30)
        preprocess_meta = _run_preprocess_stage(ingest_meta)

        _set_stage(db, job, JobState.TRANSCRIBING.value, 50)
        transcript_meta = _run_transcript_stage(job, preprocess_meta)
        _upsert_transcript_artifact(db, job, transcript_meta)

        _set_stage(db, job, JobState.FEATURE_EXTRACTING.value, 75)
        feature_meta = _run_feature_stage(job, preprocess_meta, transcript_meta)
        _upsert_feature_artifact(db, job, feature_meta)

        _set_stage(db, job, JobState.SYNTHESIZING.value, 90)
        synthesis_seed = f"{job.media_hash}:{feature_meta['quality_bucket']}:{feature_meta['source_mode']}"
        report_data = build_report(synthesis_seed, metric_overrides=feature_meta["packet_overrides"])
        report_data["pacing_timeline"] = feature_meta["timeline"]
        report = AnalysisReport(
            job_id=job.id,
            hook_score=report_data["hook_score"],
            pacing_score=report_data["pacing_score"],
            confidence=report_data["confidence"],
            report_json=report_data,
        )
        db.add(report)
        job.state = JobState.DONE.value
        job.stage = JobState.DONE.value
        job.progress = 100
        job.completed_at = datetime.now(UTC).replace(tzinfo=None)
        job.error_code = None
        db.commit()
    except Exception:
        job.state = JobState.FAILED.value
        job.stage = JobState.FAILED.value
        job.error_code = "processing_failed"
        db.commit()


def _set_stage(db: Session, job: AnalysisJob, stage: str, progress: int) -> None:
    job.state = stage
    job.stage = stage
    job.progress = progress
    db.commit()


def _run_ingest_stage(job: AnalysisJob) -> dict:
    if job.source_type == SourceType.URL.value and job.source_url:
        _validate_url(job.source_url)
        return {"ingest": "url", "duration_sec": settings.max_duration_sec, "probed": False}

    if not job.file_key:
        return {"ingest": "upload", "duration_sec": settings.max_duration_sec, "probed": False}
    try:
        path = resolve_upload_path(job.file_key)
    except ValueError:
        return {"ingest": "upload", "duration_sec": settings.max_duration_sec, "probed": False}
    if not path.exists():
        return {"ingest": "upload", "duration_sec": settings.max_duration_sec, "probed": False}
    meta = ffprobe_media(path)
    meta["ingest"] = "upload"
    meta["path"] = str(path)
    return meta


def _run_preprocess_stage(ingest_meta: dict) -> dict:
    duration = min(int(ingest_meta.get("duration_sec", settings.max_duration_sec)), settings.max_duration_sec)
    return {
        "normalized": True,
        "duration_sec": duration,
        "probed": ingest_meta.get("probed", False),
        "path": ingest_meta.get("path"),
    }


def _run_transcript_stage(job: AnalysisJob, preprocess_meta: dict) -> dict:
    media_path = preprocess_meta.get("path")
    if media_path:
        path = Path(media_path)
        text = load_transcript_sidecar(path)
        source = "sidecar" if text else "fallback"
        if not text and settings.enable_external_ai and settings.openai_api_key:
            text = transcribe_with_openai(path, settings.openai_api_key) or ""
            source = "whisper_api" if text else source
        text_meta = transcript_meta_from_text(text, preprocess_meta["duration_sec"])
        if text_meta["word_count"] > 0:
            text_meta["source"] = source
            return text_meta
    hash_hint = int(job.media_hash[:4], 16)
    quality = 0.5 + (hash_hint % 45) / 100
    return {
        "source": "fallback",
        "transcript_text": "",
        "word_count": 0,
        "speech_rate_wpm": 120 + (hash_hint % 90),
        "transcript_quality": min(0.95, quality),
    }


def _run_feature_stage(job: AnalysisJob, preprocess_meta: dict, transcript_meta: dict) -> dict:
    hash_hint = int(job.media_hash[4:8], 16)
    scene_quality = 0.4 + (hash_hint % 55) / 100
    ocr_confidence = 0.35 + ((hash_hint >> 2) % 55) / 100
    cut_frequency = 0.8 + ((hash_hint >> 4) % 35) / 10
    audio_spike = ((hash_hint >> 6) % 100) / 100
    source_mode = "fallback"

    path_str = preprocess_meta.get("path")
    if path_str:
        media_path = Path(path_str)
        maybe_scene = estimate_scene_rate_ffmpeg(media_path, preprocess_meta["duration_sec"])
        maybe_audio = estimate_audio_spike_ffmpeg(media_path)
        if maybe_scene is not None:
            cut_frequency = maybe_scene
            scene_quality = max(scene_quality, 0.65)
            source_mode = "ffmpeg"
        if maybe_audio is not None:
            audio_spike = maybe_audio
            source_mode = "ffmpeg"

    overall = (transcript_meta["transcript_quality"] + scene_quality + ocr_confidence) / 3
    if overall >= 0.75:
        quality_bucket = "high"
    elif overall >= 0.55:
        quality_bucket = "medium"
    else:
        quality_bucket = "low"

    pattern_interrupts = max(1, min(8, int(cut_frequency)))
    text_density = 0.5 if transcript_meta.get("word_count", 0) > 25 else 0.22
    first_3s_hook_density = min(0.95, 0.3 + audio_spike * 0.4 + text_density * 0.3)
    timeline = _build_pacing_timeline(
        cut_frequency=cut_frequency,
        speech_rate_wpm=int(transcript_meta["speech_rate_wpm"]),
        audio_spike=audio_spike,
        pattern_interrupts=pattern_interrupts,
    )

    return {
        "quality_bucket": quality_bucket,
        "scene_quality": scene_quality,
        "source_mode": source_mode,
        "timeline": timeline,
        "packet_overrides": {
            "transcript_quality": round(transcript_meta["transcript_quality"], 2),
            "scene_confidence": round(scene_quality, 2),
            "ocr_confidence": round(ocr_confidence, 2),
            "consistency": round((scene_quality + transcript_meta["transcript_quality"]) / 2, 2),
            "cut_frequency": round(cut_frequency, 2),
            "speech_rate_wpm": int(transcript_meta["speech_rate_wpm"]),
            "pattern_interrupts": pattern_interrupts,
            "on_screen_text_density": round(text_density, 2),
            "audio_spike": round(audio_spike, 2),
            "first_3s_hook_density": round(first_3s_hook_density, 2),
        },
    }


def usage_snapshot(db: Session, user: User) -> dict:
    day_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    jobs_used = db.query(AnalysisJob).filter(AnalysisJob.user_id == user.id, AnalysisJob.created_at >= day_start).count()
    return {
        "plan": user.plan,
        "jobs_used": jobs_used,
        "jobs_limit": settings.free_jobs_per_day,
        "minutes_used": min(jobs_used * settings.max_duration_sec // 60, 999),
        "reset_at": day_start + timedelta(days=1),
    }


def _derive_media_hash(payload: JobCreateRequest) -> str:
    if payload.source_type == SourceType.UPLOAD and payload.file_key:
        try:
            path = resolve_upload_path(payload.file_key)
            if path.exists():
                return file_sha256(path)
        except ValueError:
            pass
    return _media_hash(payload.source_type, str(payload.source_url or ""), payload.file_key)


def _build_pacing_timeline(
    cut_frequency: float,
    speech_rate_wpm: int,
    audio_spike: float,
    pattern_interrupts: int,
) -> list[dict]:
    timeline: list[dict] = []
    for i in range(0, 30, 5):
        density = cut_frequency + (i / 30) - 1
        if density < 1.8 or speech_rate_wpm < 120:
            label = "slow"
        elif density > 3.8 or speech_rate_wpm > 220:
            label = "overloaded"
        else:
            label = "optimal"
        timeline.append(
            {
                "start_sec": i,
                "end_sec": i + 5,
                "label": label,
                "notes": f"cut_density={density:.1f}, speech_wpm={speech_rate_wpm}",
                "cut_frequency": round(cut_frequency, 2),
                "speech_rate_wpm": int(speech_rate_wpm),
                "audio_spike": round(audio_spike, 2),
                "pattern_interrupts": int(pattern_interrupts),
            }
        )
    return timeline


def _upsert_transcript_artifact(db: Session, job: AnalysisJob, transcript_meta: dict) -> None:
    artifact = db.query(TranscriptArtifact).filter(TranscriptArtifact.job_id == job.id).first()
    if not artifact:
        artifact = TranscriptArtifact(job_id=job.id)
        db.add(artifact)
    artifact.source = str(transcript_meta.get("source", "fallback"))
    artifact.transcript_text = str(transcript_meta.get("transcript_text", ""))
    artifact.word_count = int(transcript_meta.get("word_count", 0))
    artifact.speech_rate_wpm = int(transcript_meta.get("speech_rate_wpm", 0))
    artifact.quality = float(transcript_meta.get("transcript_quality", 0.0))
    db.commit()


def _upsert_feature_artifact(db: Session, job: AnalysisJob, feature_meta: dict) -> None:
    artifact = db.query(FeatureArtifact).filter(FeatureArtifact.job_id == job.id).first()
    if not artifact:
        artifact = FeatureArtifact(job_id=job.id)
        db.add(artifact)
    artifact.source_mode = str(feature_meta.get("source_mode", "fallback"))
    artifact.scene_quality = float(feature_meta.get("scene_quality", 0.0))
    packet = feature_meta.get("packet_overrides", {})
    artifact.cut_frequency = float(packet.get("cut_frequency", 0.0))
    artifact.audio_spike = float(packet.get("audio_spike", 0.0))
    artifact.timeline_json = feature_meta.get("timeline", [])
    artifact.packet_overrides_json = packet
    db.commit()
