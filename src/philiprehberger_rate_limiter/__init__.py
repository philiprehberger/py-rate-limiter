"""In-memory rate limiter with sliding window and token bucket."""

from __future__ import annotations

import asyncio
import functools
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


__all__ = [
    "RateLimiter",
    "Algorithm",
    "LimitStatus",
    "RateLimitExceeded",
]


class Algorithm(Enum):
    """Rate limiting algorithm."""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass(frozen=True)
class LimitStatus:
    """Current rate limit status for a key."""

    allowed: bool
    remaining: int
    reset_at: float
    limit: int


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(self, status: LimitStatus) -> None:
        self.status = status
        super().__init__(
            f"Rate limit exceeded: {status.remaining}/{status.limit} remaining, "
            f"resets at {status.reset_at:.1f}"
        )


class RateLimiter:
    """In-memory rate limiter supporting multiple algorithms.

    Args:
        requests: Maximum number of requests allowed.
        window_seconds: Time window in seconds.
        algorithm: Rate limiting algorithm to use.
    """

    def __init__(
        self,
        requests: int,
        window_seconds: float,
        algorithm: Algorithm = Algorithm.SLIDING_WINDOW,
    ) -> None:
        if requests <= 0:
            raise ValueError("requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.requests = requests
        self.window_seconds = window_seconds
        self.algorithm = algorithm
        self._lock = threading.Lock()

        self._fixed_counts: dict[str, tuple[int, float]] = {}
        self._sliding_logs: dict[str, deque[float]] = {}
        self._bucket_state: dict[str, tuple[float, float]] = {}

    def allow(self, key: str) -> bool:
        """Check if a request is allowed for the given key.

        Args:
            key: Identifier for the rate limit subject (user ID, IP, etc.).

        Returns:
            True if the request is allowed.
        """
        return self.status(key).allowed

    def status(self, key: str) -> LimitStatus:
        """Get the current rate limit status for a key.

        Args:
            key: Identifier for the rate limit subject.

        Returns:
            LimitStatus with current state.
        """
        with self._lock:
            match self.algorithm:
                case Algorithm.FIXED_WINDOW:
                    return self._fixed_window_status(key)
                case Algorithm.SLIDING_WINDOW:
                    return self._sliding_window_status(key)
                case Algorithm.TOKEN_BUCKET:
                    return self._token_bucket_status(key)

    def reset(self, key: str) -> None:
        """Reset rate limit state for a key."""
        with self._lock:
            self._fixed_counts.pop(key, None)
            self._sliding_logs.pop(key, None)
            self._bucket_state.pop(key, None)

    def reset_all(self) -> None:
        """Reset rate limit state for all keys."""
        with self._lock:
            self._fixed_counts.clear()
            self._sliding_logs.clear()
            self._bucket_state.clear()

    def active_keys(self) -> list[str]:
        """Return a list of all keys with active rate limit state."""
        with self._lock:
            keys: set[str] = set()
            keys.update(self._fixed_counts)
            keys.update(self._sliding_logs)
            keys.update(self._bucket_state)
            return sorted(keys)

    async def async_acquire(self, key: str) -> LimitStatus:
        """Async version that awaits until quota is available.

        Loops checking ``acquire()`` and sleeping with ``asyncio.sleep()``
        for small intervals until the request is allowed.

        Args:
            key: Identifier for the rate limit subject.

        Returns:
            LimitStatus once the request is allowed.
        """
        while True:
            status = self.status(key)
            if status.allowed:
                return status
            await asyncio.sleep(0.05)

    def wait(self, key: str, timeout: float = 10.0) -> LimitStatus:
        """Synchronous blocking wait until quota is available.

        Loops calling ``acquire()`` and sleeping with ``time.sleep(0.05)``
        between attempts. Returns the status once allowed or raises
        ``RateLimitExceeded`` if *timeout* expires.

        Args:
            key: Identifier for the rate limit subject.
            timeout: Maximum time in seconds to wait before raising.

        Returns:
            LimitStatus once the request is allowed.

        Raises:
            RateLimitExceeded: If the timeout expires before quota is available.
        """
        deadline = time.monotonic() + timeout
        while True:
            status = self.status(key)
            if status.allowed:
                return status
            if time.monotonic() >= deadline:
                raise RateLimitExceeded(status)
            time.sleep(0.05)

    def limit(self, rate: str) -> Callable[..., Any]:
        """Decorator to rate-limit a function.

        Args:
            rate: Rate string like ``"10/minute"``, ``"100/hour"``, ``"5/second"``.

        Returns:
            Decorator that raises RateLimitExceeded when limit is hit.
        """
        requests, window = _parse_rate(rate)
        limiter = RateLimiter(requests, window, self.algorithm)

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key = fn.__qualname__
                status = limiter.status(key)
                if not status.allowed:
                    raise RateLimitExceeded(status)
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    def _fixed_window_status(self, key: str) -> LimitStatus:
        now = time.monotonic()
        window_start = now - (now % self.window_seconds)
        reset_at = window_start + self.window_seconds

        count, start = self._fixed_counts.get(key, (0, window_start))
        if start != window_start:
            count = 0
            start = window_start

        allowed = count < self.requests
        if allowed:
            count += 1
        self._fixed_counts[key] = (count, start)

        remaining = max(0, self.requests - count)
        return LimitStatus(allowed=allowed, remaining=remaining, reset_at=reset_at, limit=self.requests)

    def _sliding_window_status(self, key: str) -> LimitStatus:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        if key not in self._sliding_logs:
            self._sliding_logs[key] = deque()

        log = self._sliding_logs[key]
        while log and log[0] <= cutoff:
            log.popleft()

        allowed = len(log) < self.requests
        if allowed:
            log.append(now)

        remaining = max(0, self.requests - len(log))
        reset_at = log[0] + self.window_seconds if log else now + self.window_seconds
        return LimitStatus(allowed=allowed, remaining=remaining, reset_at=reset_at, limit=self.requests)

    def _token_bucket_status(self, key: str) -> LimitStatus:
        now = time.monotonic()
        rate = self.requests / self.window_seconds

        tokens, last_refill = self._bucket_state.get(key, (float(self.requests), now))
        elapsed = now - last_refill
        tokens = min(float(self.requests), tokens + elapsed * rate)
        last_refill = now

        allowed = tokens >= 1.0
        if allowed:
            tokens -= 1.0
        self._bucket_state[key] = (tokens, last_refill)

        remaining = int(tokens)
        time_to_full = (self.requests - tokens) / rate if rate > 0 else 0
        reset_at = now + time_to_full
        return LimitStatus(allowed=allowed, remaining=remaining, reset_at=reset_at, limit=self.requests)


_UNIT_MAP: dict[str, float] = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 3600,
    "hours": 3600,
    "day": 86400,
    "days": 86400,
}


def _parse_rate(rate: str) -> tuple[int, float]:
    match = re.match(r"(\d+)\s*/\s*(\w+)", rate)
    if not match:
        msg = f"Invalid rate format: '{rate}'. Expected format like '10/minute'"
        raise ValueError(msg)

    count = int(match.group(1))
    unit = match.group(2).lower()

    if unit not in _UNIT_MAP:
        msg = f"Unknown time unit: '{unit}'. Use second, minute, hour, or day"
        raise ValueError(msg)

    return count, _UNIT_MAP[unit]
