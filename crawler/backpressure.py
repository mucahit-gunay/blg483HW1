"""
Back pressure mechanisms for controlling crawler load.
- ConcurrencyLimiter: caps simultaneous HTTP requests via asyncio.Semaphore
- RateLimiter: token-bucket algorithm for per-second rate limiting
- BackPressureController: unified controller exposing metrics
"""

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class BackPressureMetrics:
    """Snapshot of current back pressure state."""
    active_workers: int = 0
    max_workers: int = 0
    queue_depth: int = 0
    max_queue_depth: int = 0
    requests_per_second: float = 0.0
    max_requests_per_second: float = 0.0
    is_throttled: bool = False
    total_requests: int = 0
    total_throttle_events: int = 0

    def to_dict(self) -> dict:
        return {
            "active_workers": self.active_workers,
            "max_workers": self.max_workers,
            "queue_depth": self.queue_depth,
            "max_queue_depth": self.max_queue_depth,
            "requests_per_second": round(self.requests_per_second, 2),
            "max_requests_per_second": self.max_requests_per_second,
            "is_throttled": self.is_throttled,
            "total_requests": self.total_requests,
            "total_throttle_events": self.total_throttle_events,
        }


class ConcurrencyLimiter:
    """Limits concurrent HTTP requests using asyncio.Semaphore."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self._semaphore.acquire()
        async with self._lock:
            self._active += 1

    async def release(self):
        self._semaphore.release()
        async with self._lock:
            self._active -= 1

    @property
    def active(self) -> int:
        return self._active

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        await self.release()


class RateLimiter:
    """Token-bucket rate limiter. Limits requests per second."""

    def __init__(self, max_per_second: float = 20.0):
        self.max_per_second = max_per_second
        self._tokens = max_per_second
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._request_times: list[float] = []
        self._total_requests = 0
        self._total_throttles = 0

    async def acquire(self):
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(
                    self.max_per_second,
                    self._tokens + elapsed * self.max_per_second,
                )
                self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    self._total_requests += 1
                    self._request_times.append(now)
                    # Keep only last 5 seconds of requests for RPS calculation
                    cutoff = now - 5.0
                    self._request_times = [t for t in self._request_times if t > cutoff]
                    return

                self._total_throttles += 1

            # Not enough tokens — wait a bit
            await asyncio.sleep(1.0 / self.max_per_second)

    @property
    def current_rps(self) -> float:
        now = time.monotonic()
        cutoff = now - 5.0
        recent = [t for t in self._request_times if t > cutoff]
        if len(recent) < 2:
            return 0.0
        span = recent[-1] - recent[0]
        return len(recent) / span if span > 0 else 0.0

    @property
    def total_requests(self) -> int:
        return self._total_requests

    @property
    def total_throttles(self) -> int:
        return self._total_throttles


class BackPressureController:
    """Unified controller combining concurrency + rate limiting + queue depth."""

    def __init__(
        self,
        max_concurrent: int = 10,
        max_per_second: float = 20.0,
        max_queue_depth: int = 10000,
    ):
        self.concurrency = ConcurrencyLimiter(max_concurrent)
        self.rate_limiter = RateLimiter(max_per_second)
        self.max_queue_depth = max_queue_depth
        self._current_queue_depth = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Acquire both concurrency slot and rate limit token."""
        await self.concurrency.acquire()
        await self.rate_limiter.acquire()

    async def release(self):
        """Release concurrency slot."""
        await self.concurrency.release()

    async def set_queue_depth(self, depth: int):
        async with self._lock:
            self._current_queue_depth = depth

    def can_enqueue(self) -> bool:
        """Check if the queue has room for more URLs."""
        return self._current_queue_depth < self.max_queue_depth

    @property
    def is_throttled(self) -> bool:
        return (
            self.concurrency.active >= self.concurrency.max_concurrent
            or self._current_queue_depth >= self.max_queue_depth
        )

    def get_metrics(self) -> BackPressureMetrics:
        return BackPressureMetrics(
            active_workers=self.concurrency.active,
            max_workers=self.concurrency.max_concurrent,
            queue_depth=self._current_queue_depth,
            max_queue_depth=self.max_queue_depth,
            requests_per_second=self.rate_limiter.current_rps,
            max_requests_per_second=self.rate_limiter.max_per_second,
            is_throttled=self.is_throttled,
            total_requests=self.rate_limiter.total_requests,
            total_throttle_events=self.rate_limiter.total_throttles,
        )
