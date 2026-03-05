from enum import Enum


class SourceType(str, Enum):
    URL = "url"
    UPLOAD = "upload"


class JobState(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PREPROCESSING = "preprocessing"
    TRANSCRIBING = "transcribing"
    FEATURE_EXTRACTING = "feature_extracting"
    SYNTHESIZING = "synthesizing"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"
    EXPIRED = "expired"
