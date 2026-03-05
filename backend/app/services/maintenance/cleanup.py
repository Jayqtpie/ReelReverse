from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from ...config import settings


def _cleanup_dir(root: Path, older_than: timedelta) -> int:
    if not root.exists():
        return 0
    threshold = datetime.now(UTC) - older_than
    removed = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=UTC)
            if mtime < threshold:
                p.unlink(missing_ok=True)
                removed += 1
        except Exception:
            continue
    return removed


def run_retention_cleanup() -> dict:
    media_removed = _cleanup_dir(Path(settings.media_dir), timedelta(hours=settings.media_ttl_hours))
    export_removed = _cleanup_dir(Path(settings.export_dir), timedelta(hours=1))
    return {"media_removed": media_removed, "export_removed": export_removed}
