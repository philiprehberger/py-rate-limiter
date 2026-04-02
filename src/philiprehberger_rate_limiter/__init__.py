"""In-memory rate limiter with sliding window, token bucket, and leaky bucket algorithms."""

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
    "RateLimiterGroup",
    "RateLimiterStats",
    "rate_limit",
]


class Algorithm(Enum):
    """Rate limiting algorithm."""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass(frozen=True)
class LimitStatus:
    """Current rate limit status for a key."""

    allowed: bool
    remaining: int
    reset_at: float
    limit: int


@dataclass(frozen=True)
class RateLimiterStats:
    """Statistics for a rate limiter key.

    Attributes:
        current_usage: Number of requests consumed in the current window.
        remaining: Number of requests remaining.
        reset_at: Monotonic timestamp when the window resets or bucket refills.
        limit: Maximum requests allowed.
    """

    current_usage: int
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
        self._leaky_state: dict[str, tuple[float, float]] = {}

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
                case Algorithm.LEAKY_BUCKET:
                    return self._leaky_bucket_status(key)

    def reset(self, key: str) -> None:
        """Reset rate limit state for a key."""
        with self._lock:
            self._fixed_counts.pop(key, None)
            self._sliding_logs.pop(key, None)
            self._bucket_state.pop(key, None)
            self._leaky_state.pop(key, None)

    def reset_all(self) -> None:
        """Reset rate limit state for all keys."""
        with self._lock:
            self._fixed_counts.clear()
            self._sliding_logs.clear()
            self._bucket_state.clear()
            self._leaky_state.clear()

    def active_keys(self) -> list[str]:
        """Return a list of all keys with active rate limit state."""
        with self._lock:
            keys: set[str] = set()
            keys.update(self._fixed_counts)
            keys.update(self._sliding_logs)
            keys.update(self._bucket_state)
            keys.update(self._leaky_state)
            return sorted(keys)

    def get_stats(self, key: str) -> RateLimiterStats:
        """Get current usage statistics for a key without consuming a request.

        Args:
            key: Identifier for the rate limit subject.

        Returns:
            RateLimiterStats with current usage, remaining tokens, and reset time.
        """
        with self._lock:
            match self.algorithm:
                case Algorithm.FIXED_WINDOW:
                    return self._fixed_window_stats(key)
                case Algorithm.SLIDING_WINDOW:
                    return self._sliding_window_stats(key)
                case Algorithm.TOKEN_BUCKET:
                    return self._token_bucket_stats(key)
                case Algorithm.LEAKY_BUCKET:
                    return self._leaky_bucket_stats(key)

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

    async def __aenter__(self) -> RateLimiter:
        """Enter the async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit the async context manager."""

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

    # --- Stats methods (read-only, no consumption) ---

    def _fixed_window_stats(self, key: str) -> RateLimiterStats:
        now = time.monotonic()
        window_start = now - (now % self.window_seconds)
        reset_at = window_start + self.window_seconds

        count, start = self._fixed_counts.get(key, (0, window_start))
        if start != window_start:
            count = 0

        remaining = max(0, self.requests - count)
        return RateLimiterStats(
            current_usage=count,
            remaining=remaining,
            reset_at=reset_at,
            limit=self.requests,
        )

    def _sliding_window_stats(self, key: str) -> RateLimiterStats:
        now = time.monotonic()
        cutoff = now - self.window_seconds

        if key not in self._sliding_logs:
            return RateLimiterStats(
                current_usage=0,
                remaining=self.requests,
                reset_at=now + self.window_seconds,
                limit=self.requests,
            )

        log = self._sliding_logs[key]
        # Count entries within window without modifying
        usage = sum(1 for t in log if t > cutoff)
        remaining = max(0, self.requests - usage)
        reset_at = log[0] + self.window_seconds if log else now + self.window_seconds
        return RateLimiterStats(
            current_usage=usage,
            remaining=remaining,
            reset_at=reset_at,
            limit=self.requests,
        )

    def _token_bucket_stats(self, key: str) -> RateLimiterStats:
        now = time.monotonic()
        rate = self.requests / self.window_seconds

        tokens, last_refill = self._bucket_state.get(key, (float(self.requests), now))
        elapsed = now - last_refill
        tokens = min(float(self.requests), tokens + elapsed * rate)

        remaining = int(tokens)
        current_usage = self.requests - remaining
        time_to_full = (self.requests - tokens) / rate if rate > 0 else 0
        reset_at = now + time_to_full
        return RateLimiterStats(
            current_usage=current_usage,
            remaining=remaining,
            reset_at=reset_at,
            limit=self.requests,
        )

    def _leaky_bucket_stats(self, key: str) -> RateLimiterStats:
        now = time.monotonic()
        leak_rate = self.requests / self.window_seconds

        water_level, last_check = self._leaky_state.get(key, (0.0, now))
        elapsed = now - last_check
        water_level = max(0.0, water_level - elapsed * leak_rate)

        current_usage = int(water_level)
        remaining = max(0, self.requests - current_usage)
        time_to_empty = water_level / leak_rate if leak_rate > 0 else 0
        reset_at = now + time_to_empty
        return RateLimiterStats(
            current_usage=current_usage,
            remaining=remaining,
            reset_at=reset_at,
            limit=self.requests,
        )

    # --- Algorithm implementations ---

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

    def _leaky_bucket_status(self, key: str) -> LimitStatus:
        """Leaky bucket algorithm.

        The bucket fills with each request and leaks at a constant rate.
        Requests are allowed as long as the bucket is not full.
        """
        now = time.monotonic()
        leak_rate = self.requests / self.window_seconds

        water_level, last_check = self._leaky_state.get(key, (0.0, now))
        elapsed = now - last_check
        water_level = max(0.0, water_level - elapsed * leak_rate)
        last_check = now

        allowed = water_level + 1.0 <= float(self.requests)
        if allowed:
            water_level += 1.0
        self._leaky_state[key] = (water_level, last_check)

        remaining = max(0, int(float(self.requests) - water_level))
        time_to_empty = water_level / leak_rate if leak_rate > 0 else 0
        reset_at = now + time_to_empty
        return LimitStatus(allowed=allowed, remaining=remaining, reset_at=reset_at, limit=self.requests)


class RateLimiterGroup:
    """Apply shared rate limits across multiple keys.

    A group enforces a single shared limit that is consumed whenever
    any key in the group makes a request.

    Args:
        limiter: The underlying RateLimiter instance.
        keys: Keys that share the same rate limit pool.
    """

    def __init__(self, limiter: RateLimiter, keys: list[str]) -> None:
        self._limiter = limiter
        self._keys = list(keys)
        self._group_key = "::group::" + ",".join(sorted(self._keys))

    @property
    def keys(self) -> list[str]:
        """Return the list of keys in this group."""
        return list(self._keys)

    def allow(self, key: str) -> bool:
        """Check if a request is allowed for a key in this group.

        All keys in the group share a single rate limit pool.

        Args:
            key: The requesting key (must be in the group).

        Returns:
            True if the request is allowed.

        Raises:
            ValueError: If the key is not part of this group.
        """
        if key not in self._keys:
            raise ValueError(f"Key '{key}' is not part of this group")
        return self._limiter.allow(self._group_key)

    def status(self, key: str) -> LimitStatus:
        """Get the shared rate limit status.

        Args:
            key: The requesting key (must be in the group).

        Returns:
            LimitStatus for the shared pool.

        Raises:
            ValueError: If the key is not part of this group.
        """
        if key not in self._keys:
            raise ValueError(f"Key '{key}' is not part of this group")
        return self._limiter.status(self._group_key)

    def get_stats(self) -> RateLimiterStats:
        """Get usage statistics for the shared group pool.

        Returns:
            RateLimiterStats for the group.
        """
        return self._limiter.get_stats(self._group_key)

    def reset(self) -> None:
        """Reset the shared rate limit state for this group."""
        self._limiter.reset(self._group_key)


def rate_limit(
    calls: int,
    period: float,
    algorithm: Algorithm = Algorithm.SLIDING_WINDOW,
) -> Callable[..., Any]:
    """Standalone decorator to rate-limit a function.

    Args:
        calls: Maximum number of calls allowed in the period.
        period: Time period in seconds.
        algorithm: Rate limiting algorithm to use.

    Returns:
        Decorator that raises RateLimitExceeded when limit is hit.

    Example::

        @rate_limit(calls=10, period=60)
        def my_function():
            ...
    """
    limiter = RateLimiter(calls, period, algorithm)

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                key = fn.__qualname__
                status = limiter.status(key)
                if not status.allowed:
                    raise RateLimitExceeded(status)
                return await fn(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(fn)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                key = fn.__qualname__
                status = limiter.status(key)
                if not status.allowed:
                    raise RateLimitExceeded(status)
                return fn(*args, **kwargs)
            return wrapper
    return decorator


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
