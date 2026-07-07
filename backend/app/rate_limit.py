"""In-memory per-IP rate limiting for the public /scan endpoint.

No Redis/external store -- this runs as a single container instance, so a
plain in-process token bucket per client IP is sufficient. Restarting the
container resets limits, which is an acceptable tradeoff for a free tool.
"""
from __future__ import annotations

import threading
import time

_MAX_TRACKED_IPS = 5000
_STALE_AFTER_SECONDS = 60 * 60  # drop buckets untouched for an hour


class TokenBucket:
    def __init__(self, capacity: float, refill_per_sec: float):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self.tokens = capacity
        self.last_check = time.monotonic()

    def allow(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_check
        self.last_check = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimiter:
    """capacity=5, refill_per_sec=1/30 => burst of 5 scans, then ~1 every 30s per IP."""

    def __init__(self, capacity: int = 5, refill_per_sec: float = 1 / 30):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._buckets: dict[str, TokenBucket] = {}
        self._touched: dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, client_ip: str) -> bool:
        with self._lock:
            self._maybe_sweep()
            bucket = self._buckets.get(client_ip)
            if bucket is None:
                bucket = TokenBucket(self.capacity, self.refill_per_sec)
                self._buckets[client_ip] = bucket
            self._touched[client_ip] = time.monotonic()
            return bucket.allow()

    def _maybe_sweep(self) -> None:
        if len(self._buckets) <= _MAX_TRACKED_IPS:
            return
        cutoff = time.monotonic() - _STALE_AFTER_SECONDS
        stale = [ip for ip, ts in self._touched.items() if ts < cutoff]
        for ip in stale:
            self._buckets.pop(ip, None)
            self._touched.pop(ip, None)
