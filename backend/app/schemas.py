from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from .enums import JobState, SourceType


class JobCreateRequest(BaseModel):
    source_type: SourceType
    source_url: HttpUrl | None = None
    file_key: str | None = None
    duration_sec: int | None = Field(default=None, ge=1)
    confirm_rights: bool

    @model_validator(mode="after")
    def validate_input(self) -> "JobCreateRequest":
        if not self.confirm_rights:
            raise ValueError("confirm_rights must be true")
        if self.source_type == SourceType.URL and not self.source_url:
            raise ValueError("source_url is required for url source_type")
        if self.source_type == SourceType.UPLOAD and not self.file_key:
            raise ValueError("file_key is required for upload source_type")
        return self


class JobCreateResponse(BaseModel):
    job_id: str
    state: JobState
    eta_seconds: int


class JobStatusResponse(BaseModel):
    job_id: str
    state: JobState
    progress: int
    stage: str
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class HookAnalysis(BaseModel):
    score: int
    verdict: str
    reasons: list[str]


class PacingBucket(BaseModel):
    start_sec: int
    end_sec: int
    label: Literal["slow", "optimal", "overloaded"]
    notes: str
    cut_frequency: float | None = None
    speech_rate_wpm: int | None = None
    audio_spike: float | None = None
    pattern_interrupts: int | None = None


class CaptionFormula(BaseModel):
    pattern: str
    slots: dict[str, str]


class RemakeTemplate(BaseModel):
    anti_plagiarism_notice: str
    sections: list[dict[str, str]]


class ArtifactMetadata(BaseModel):
    transcript_source: str
    transcript_quality: float
    transcript_word_count: int
    feature_source_mode: str
    scene_quality: float
    cut_frequency: float
    audio_spike: float


class ReportResponse(BaseModel):
    job_id: str
    hook_analysis: HookAnalysis
    pacing_timeline: list[PacingBucket]
    caption_formula: CaptionFormula
    remake_template: RemakeTemplate
    artifacts: ArtifactMetadata
    confidence: float
    generated_at: datetime


class ArtifactsResponse(BaseModel):
    job_id: str
    transcript: dict
    features: dict


class TimelineResponse(BaseModel):
    job_id: str
    timeline: list[PacingBucket]


class ReportListItem(BaseModel):
    job_id: str
    state: JobState
    created_at: datetime
    confidence: float | None = None


class ReportListResponse(BaseModel):
    items: list[ReportListItem]
    next_cursor: str | None = None


class ExportRequest(BaseModel):
    format: Literal["pdf", "json"]


class ExportResponse(BaseModel):
    download_url: str
    expires_at: datetime


class UsageResponse(BaseModel):
    plan: str
    jobs_used: int
    jobs_limit: int
    minutes_used: int
    reset_at: datetime


class UploadPresignRequest(BaseModel):
    filename: str = Field(min_length=3, max_length=255)


class UploadPresignResponse(BaseModel):
    file_key: str
    upload_url: str
    max_upload_mb: int
