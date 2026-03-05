from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import settings


def create_export_artifact(job_id: str, user_id: str, fmt: str, report_json: dict) -> dict:
    export_dir = Path(settings.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    expiry_ts = int(expires.timestamp())

    if fmt == "json":
        artifact_name = f"{job_id}.json"
        artifact_path = export_dir / artifact_name
        artifact_path.write_text(json.dumps(report_json, indent=2), encoding="utf-8")
    else:
        artifact_name = f"{job_id}.pdf"
        artifact_path = export_dir / artifact_name
        artifact_path.write_bytes(_minimal_pdf_bytes(job_id, report_json))

    token = sign_export_token(user_id=user_id, job_id=job_id, fmt=fmt, expires_ts=expiry_ts)
    return {
        "download_url": f"/v1/reports/download/{token}",
        "expires_at": expires,
        "artifact_path": str(artifact_path),
    }


def sign_export_token(user_id: str, job_id: str, fmt: str, expires_ts: int) -> str:
    payload = f"{user_id}:{job_id}:{fmt}:{expires_ts}"
    sig = hmac.new(
        settings.export_signing_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    token_raw = f"{payload}:{sig}"
    return base64.urlsafe_b64encode(token_raw.encode("utf-8")).decode("utf-8").rstrip("=")


def verify_export_token(token: str) -> dict:
    padded = token + "=" * ((4 - len(token) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        user_id, job_id, fmt, expires_ts, sig = decoded.split(":")
    except Exception as exc:
        raise ValueError("invalid_export_token") from exc

    payload = f"{user_id}:{job_id}:{fmt}:{expires_ts}"
    expected = hmac.new(
        settings.export_signing_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise ValueError("invalid_export_token_signature")
    if int(expires_ts) < int(datetime.now(timezone.utc).timestamp()):
        raise ValueError("expired_export_token")
    if fmt not in {"json", "pdf"}:
        raise ValueError("invalid_export_format")
    return {"user_id": user_id, "job_id": job_id, "format": fmt}


def _minimal_pdf_bytes(job_id: str, report_json: dict) -> bytes:
    summary = f"ReelRev Report {job_id}\\nHook: {report_json.get('hook_score')}\\nPacing: {report_json.get('pacing_score')}"
    content = f"BT /F1 12 Tf 50 760 Td ({summary}) Tj ET"
    pdf = (
        "%PDF-1.4\n"
        "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
        f"4 0 obj<< /Length {len(content)} >>stream\n{content}\nendstream endobj\n"
        "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        "xref\n0 6\n0000000000 65535 f \n"
        "0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n"
        "0000000245 00000 n \n0000000000 00000 n \n"
        "trailer<< /Root 1 0 R /Size 6 >>\nstartxref\n360\n%%EOF\n"
    )
    return pdf.encode("utf-8", errors="ignore")
