from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(32), default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="user")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (UniqueConstraint("user_id", "media_hash", name="uq_user_media_hash"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_hash: Mapped[str] = mapped_column(String(64), index=True)
    state: Mapped[str] = mapped_column(String(32), index=True, default="queued")
    stage: Mapped[str] = mapped_column(String(64), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    confirm_rights: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="jobs")
    report: Mapped["AnalysisReport"] = relationship(back_populates="job", uselist=False)
    transcript_artifact: Mapped["TranscriptArtifact"] = relationship(back_populates="job", uselist=False)
    feature_artifact: Mapped["FeatureArtifact"] = relationship(back_populates="job", uselist=False)


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_jobs.id"), unique=True)
    hook_score: Mapped[int] = mapped_column(Integer)
    pacing_score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column()
    report_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    job: Mapped["AnalysisJob"] = relationship(back_populates="report")


class TranscriptArtifact(Base):
    __tablename__ = "transcript_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_jobs.id"), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="fallback")
    transcript_text: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    speech_rate_wpm: Mapped[int] = mapped_column(Integer, default=0)
    quality: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    job: Mapped["AnalysisJob"] = relationship(back_populates="transcript_artifact")


class FeatureArtifact(Base):
    __tablename__ = "feature_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_jobs.id"), unique=True, index=True)
    source_mode: Mapped[str] = mapped_column(String(32), default="fallback")
    scene_quality: Mapped[float] = mapped_column(default=0.0)
    cut_frequency: Mapped[float] = mapped_column(default=0.0)
    audio_spike: Mapped[float] = mapped_column(default=0.0)
    timeline_json: Mapped[dict] = mapped_column(JSON, default=dict)
    packet_overrides_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    job: Mapped["AnalysisJob"] = relationship(back_populates="feature_artifact")
