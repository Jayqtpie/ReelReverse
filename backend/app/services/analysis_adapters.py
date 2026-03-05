from __future__ import annotations

import re
import subprocess
from pathlib import Path

import httpx


def load_transcript_sidecar(media_path: Path) -> str:
    for ext in (".txt", ".srt", ".vtt"):
        candidate = media_path.with_suffix(ext)
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                return ""
    return ""


def transcript_meta_from_text(text: str, duration_sec: int) -> dict:
    words = re.findall(r"[A-Za-z0-9']+", text)
    wc = len(words)
    minutes = max(duration_sec / 60, 0.25)
    speech_rate_wpm = int(wc / minutes) if wc else 0
    quality = 0.35 + min(0.6, wc / 240)
    if wc == 0:
        quality = 0.42
        speech_rate_wpm = 150
    return {
        "transcript_text": text,
        "word_count": wc,
        "speech_rate_wpm": max(80, min(260, speech_rate_wpm)),
        "transcript_quality": round(max(0.2, min(0.95, quality)), 2),
    }


def transcribe_with_openai(media_path: Path, api_key: str) -> str | None:
    if not api_key or not media_path.exists():
        return None
    try:
        with media_path.open("rb") as f:
            files = {"file": (media_path.name, f, "application/octet-stream")}
            data = {"model": "gpt-4o-mini-transcribe"}
            response = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files=files,
                data=data,
                timeout=120,
            )
        if response.status_code >= 300:
            return None
        body = response.json()
        text = body.get("text")
        return text if isinstance(text, str) and text.strip() else None
    except Exception:
        return None


def estimate_scene_rate_ffmpeg(media_path: Path, duration_sec: int) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(media_path),
                "-vf",
                "select='gt(scene,0.35)',showinfo",
                "-f",
                "null",
                "NUL",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception:
        return None
    scene_hits = len(re.findall(r"showinfo", result.stderr or ""))
    if duration_sec <= 0:
        return None
    return round(max(0.8, min(5.0, scene_hits / duration_sec * 5)), 2)


def estimate_audio_spike_ffmpeg(media_path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(media_path),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "NUL",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception:
        return None
    stderr = result.stderr or ""
    mean_match = re.search(r"mean_volume:\s*(-?\d+(\.\d+)?) dB", stderr)
    max_match = re.search(r"max_volume:\s*(-?\d+(\.\d+)?) dB", stderr)
    if not mean_match or not max_match:
        return None
    mean_db = float(mean_match.group(1))
    max_db = float(max_match.group(1))
    delta = max(0.0, min(18.0, max_db - mean_db))
    return round(delta / 18.0, 2)
