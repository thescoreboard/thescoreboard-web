"""
Lightweight in-memory per-IP rate limiting — no external dependency.

Suitable for a single-instance deployment (Render). If the backend ever
scales to multiple instances, move this state to Redis.

Note on limits: at a live venue most attendees share ONE public IP (venue
WiFi NAT), so per-IP limits on login must stay generous enough for a burst
of legitimate sign-ins at event start.
"""
import threading
import time
from collections import deque

from fastapi import HTTPException, Request


class RateLimiter:
    """FastAPI dependency: at most `max_requests` per `window_seconds` per client IP."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: dict = {}          # ip → deque[monotonic timestamps]
        self._lock = threading.Lock()

    @staticmethod
    def _client_ip(request: Request) -> str:
        # Render terminates TLS at a proxy — the real client IP is the first
        # entry of X-Forwarded-For.
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def reset(self) -> None:
        """Testing hook — clear all recorded hits."""
        with self._lock:
            self._hits.clear()

    def __call__(self, request: Request) -> None:
        ip = self._client_ip(request)
        now = time.monotonic()
        with self._lock:
            q = self._hits.get(ip)
            if q is None:
                q = self._hits[ip] = deque()
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_requests:
                retry_after = max(1, int(self.window - (now - q[0])) + 1)
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests — please wait a moment and try again.",
                    headers={"Retry-After": str(retry_after)},
                )
            q.append(now)

            # Opportunistic cleanup so the dict can't grow unbounded
            if len(self._hits) > 10_000:
                stale = [k for k, v in self._hits.items()
                         if not v or now - v[-1] > self.window]
                for k in stale:
                    self._hits.pop(k, None)


# ── Shared instances ──────────────────────────────────────────
# login/google: generous — a whole venue can sit behind one NAT IP
login_limiter               = RateLimiter(30, 60)
register_limiter            = RateLimiter(10, 60)
public_registration_limiter = RateLimiter(5, 60)
