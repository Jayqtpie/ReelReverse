from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from ..config import settings


def media_root() -> Path:
    root = Path(settings.media_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_upload_path(file_key: str) -> Path:
    sanitized = file_key.strip().replace("\\", "/").lstrip("/")
    candidate = (media_root() / sanitized).resolve()
    if media_root().resolve() not in candidate.parents and candidate != media_root().resolve():
        raise ValueError("invalid_file_key")
    return candidate


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ffprobe_media(path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_entries",
                "format=duration,size:stream=codec_type,width,height,r_frame_rate",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return {"duration_sec": settings.max_duration_sec, "width": 1080, "height": 1920, "fps": 30.0, "probed": False}

    parsed = json.loads(result.stdout or "{}")
    duration = float((parsed.get("format") or {}).get("duration") or settings.max_duration_sec)
    streams = parsed.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    r_frame_rate = str(video.get("r_frame_rate") or "30/1")
    if "/" in r_frame_rate:
        num, den = r_frame_rate.split("/", 1)
        fps = float(num) / max(float(den), 1.0)
    else:
        fps = float(r_frame_rate)
    return {
        "duration_sec": int(round(duration)),
        "width": int(video.get("width") or 1080),
        "height": int(video.get("height") or 1920),
        "fps": round(fps, 2),
        "probed": True,
    }
