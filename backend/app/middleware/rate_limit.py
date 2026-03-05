from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse

from ..config import settings

_burst_hits: dict[str, deque[float]] = defaultdict(deque)
_daily_hits: dict[str, tuple[str, int]] = {}
_lock = Lock()


def _principal(request: Request) -> str | None:
    if request.url.path in {"/healthz"}:
        return None
    email = request.headers.get("x-user-email")
    if email:
        return email.lower().strip()
    auth = request.headers.get("authorization")
    if auth:
        return f"auth:{auth[:18]}"
    return None


async def rate_limit_middleware(request: Request, call_next):
    key = _principal(request)
    if not key:
        return await call_next(request)

    now = datetime.now(UTC)
    now_ts = now.timestamp()
    day_key = now.strftime("%Y-%m-%d")

    with _lock:
        burst = _burst_hits[key]
        while burst and (now_ts - burst[0]) > 60:
            burst.popleft()
        if len(burst) >= settings.rate_limit_burst_per_min:
            return JSONResponse(status_code=429, content={"detail": "rate_limit_burst_exceeded"})
        burst.append(now_ts)

        stored_day, count = _daily_hits.get(key, (day_key, 0))
        if stored_day != day_key:
            stored_day, count = day_key, 0
        if count >= settings.rate_limit_daily_requests:
            return JSONResponse(status_code=429, content={"detail": "rate_limit_daily_exceeded"})
        _daily_hits[key] = (stored_day, count + 1)

    return await call_next(request)
