from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ReelRev API"
    env: str = "dev"
    database_url: str = "sqlite:///./reelrev.db"
    redis_url: str = "redis://localhost:6379/0"
    media_ttl_hours: int = 24
    report_retention_days: int = 90
    free_jobs_per_day: int = 5
    max_duration_sec: int = 90
    max_upload_mb: int = 250
    queue_mode: str = "inline"
    auth_mode: str = "header"
    supabase_jwt_secret: str = ""
    media_dir: str = "./media"
    openai_api_key: str = ""
    enable_external_ai: bool = False
    cors_origins: str = "http://localhost:3000"
    export_dir: str = "./exports"
    export_signing_secret: str = "dev-export-secret"
    rate_limit_burst_per_min: int = 120
    rate_limit_daily_requests: int = 2000
    model_config = SettingsConfigDict(env_file=".env", env_prefix="REELREV_")


settings = Settings()
