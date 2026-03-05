# ReelRev MVP

Backend-first implementation of the Reel Reverse-Engineer Tool MVP.

## What is implemented
- FastAPI v1 endpoints:
  - `POST /v1/jobs`
  - `GET /v1/jobs/{job_id}`
  - `GET /v1/reports/{job_id}`
  - `GET /v1/reports/{job_id}/artifacts`
  - `GET /v1/reports/{job_id}/timeline`
  - `GET /v1/reports`
  - `POST /v1/reports/{job_id}/export`
  - `POST /v1/maintenance/cleanup`
  - `GET /v1/usage`
- Job lifecycle model (`queued -> ... -> done/failed`)
- Inline queue execution by default (`REELREV_QUEUE_MODE=inline`) with optional Celery mode (`REELREV_QUEUE_MODE=celery`)
- Upload bootstrap API:
  - `POST /v1/uploads/presign`
  - `PUT /v1/uploads/{file_key}`
- Deterministic analysis engine for:
  - Hook analysis
  - Pacing timeline
  - Caption formula extraction
  - Remake template generation
- Legal-safe output copy and rights confirmation enforcement
- Minimal Next.js frontend shell

## Quickstart
1. Backend
```bash
cd backend
py -3.12 -m venv .venv
. .venv/Scripts/activate
py -3.12 -m pip install -r requirements.txt
py -3.12 -m uvicorn app.main:app --reload
```

2. Run tests
```bash
cd backend
py -3.12 -m pytest
```

3. Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

4. Worker (optional but recommended)
```bash
cd backend
py -3.12 -m celery -A app.worker.celery_app.celery_app worker --loglevel=info
```

## Auth model for local development
Use request header `x-user-email` as a lightweight stand-in for JWT auth during MVP bootstrap.
- `REELREV_AUTH_MODE=header` (default): uses `x-user-email`.
- `REELREV_AUTH_MODE=jwt`: expects `Authorization: Bearer <token>` and validates HS256 token with `REELREV_SUPABASE_JWT_SECRET`.
- Browser access from local frontend is enabled via `REELREV_CORS_ORIGINS` (default `http://localhost:3000`).
- Request rate limiting is enabled:
  - `REELREV_RATE_LIMIT_BURST_PER_MIN` (default `120`)
  - `REELREV_RATE_LIMIT_DAILY_REQUESTS` (default `2000`)

## Current implementation limits
- URL ingest currently allows YouTube domains only.
- Pipeline has explicit ingest/preprocess/transcript/feature/synthesis stage handlers.
- Upload ingest now computes content hash from saved file and uses `ffprobe` metadata when available (fallback defaults otherwise).
- Feature extraction now consumes measured signals when available:
  - scene-change density from FFmpeg scene filter
  - audio spike proxy from FFmpeg `volumedetect`
  - transcript quality/speech rate from sidecar transcript files (`.txt/.srt/.vtt`) when present
- Transcript and feature artifacts are persisted per job for debugging/replay (`transcript_artifacts`, `feature_artifacts` tables).
- Report payload now includes artifact provenance metadata (`artifacts`) for frontend transparency.
- Timeline entries now include numeric pacing metrics (`cut_frequency`, `speech_rate_wpm`, `audio_spike`, `pattern_interrupts`) and can be fetched directly from `/timeline`.
- Frontend report view now renders a pacing chart (cuts, speech rate, audio spike) from timeline data.
- Frontend upload flow now supports binary file upload using `/v1/uploads/presign` + `PUT /v1/uploads/{file_key}` before job submission.
- Frontend report view now includes export actions for JSON/PDF.

Retention cleanup:
- `POST /v1/maintenance/cleanup` removes expired files from `media/` and `exports/`.
- In `celery` mode it queues a cleanup task; in `inline` mode it runs immediately.
- Report export now generates file artifacts under `REELREV_EXPORT_DIR` and returns signed download URLs.

Optional external STT:
- Set `REELREV_ENABLE_EXTERNAL_AI=true` and `REELREV_OPENAI_API_KEY=<key>` to enable Whisper API transcription when no transcript sidecar is found.
