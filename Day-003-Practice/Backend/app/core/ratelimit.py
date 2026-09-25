"""Login throttling and account lockout.

A sliding window per key, held in process memory. That is the right trade for a
single-node deployment and honest about its limit: with several uvicorn workers
each keeps its own counters, so the effective allowance is per worker. Move the
counters to Redis when you scale out horizontally.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.config import settings


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: int, lockout_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = window_seconds
        self.lockout = lockout_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._locked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> int:
        """Seconds the caller must wait, or 0 if they may proceed."""
        now = time.monotonic()
        with self._lock:
            until = self._locked_until.get(key)
            if until and until > now:
                return int(until - now) + 1
            if until:
                del self._locked_until[key]
            return 0

    def record_failure(self, key: str) -> int:
        """Log a failed attempt. Returns attempts remaining before lockout."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window:
                hits.popleft()
            hits.append(now)
            if len(hits) >= self.max_attempts:
                self._locked_until[key] = now + self.lockout
                hits.clear()
                return 0
            return self.max_attempts - len(hits)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)
            self._locked_until.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()
            self._locked_until.clear()


login_limiter = SlidingWindowLimiter(
    max_attempts=settings.LOGIN_MAX_ATTEMPTS,
    window_seconds=settings.LOGIN_WINDOW_SECONDS,
    lockout_seconds=settings.LOGIN_LOCKOUT_SECONDS,
)
