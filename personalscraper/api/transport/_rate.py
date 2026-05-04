"""Token-bucket rate limiter.

Implements DESIGN S3.6: thread-safe RateLimiter used by HttpTransport
when policy.rate_limit.requests_per_second > 0.
"""

import time
from threading import Lock


class RateLimiter:
    """Token-bucket rate limiter for API throttling.

    When requests_per_second is 0, acquire() is a no-op.
    Thread-safe via an internal Lock.

    Attributes:
        rate: Max requests per second. 0.0 = disabled.
    """

    def __init__(self, rate: float) -> None:
        self._rate = rate
        self._lock = Lock()
        self._tokens: float = 0.0
        self._refill_time: float = 1.0 / max(rate, 0.001)

    def acquire(self) -> None:
        """Block until a token is available, or return immediately if rate=0."""
        if self._rate <= 0:
            return
        with self._lock:
            now = time.monotonic()
            if now >= self._tokens:
                self._tokens = now + self._refill_time
                return
            wait = self._tokens - now
            self._tokens += self._refill_time
        if wait > 0:
            time.sleep(wait)
