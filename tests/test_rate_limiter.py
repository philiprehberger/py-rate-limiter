import asyncio

import pytest
from philiprehberger_rate_limiter import (
    RateLimiter,
    RateLimiterGroup,
    RateLimiterStats,
    Algorithm,
    LimitStatus,
    RateLimitExceeded,
    rate_limit,
)


# --- Existing tests (v0.1.0 - v0.3.1) ---


def test_sliding_window_allows():
    limiter = RateLimiter(5, 60.0)
    assert limiter.allow("user1") is True


def test_sliding_window_exhausts():
    limiter = RateLimiter(3, 60.0)
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is False


def test_status_returns_limit_status():
    limiter = RateLimiter(5, 60.0)
    status = limiter.status("user1")
    assert isinstance(status, LimitStatus)
    assert status.allowed is True
    assert status.limit == 5


def test_remaining_decreases():
    limiter = RateLimiter(3, 60.0)
    limiter.allow("user1")
    status = limiter.status("user1")
    assert status.remaining < 3


def test_reset():
    limiter = RateLimiter(2, 60.0)
    limiter.allow("user1")
    limiter.allow("user1")
    assert limiter.allow("user1") is False
    limiter.reset("user1")
    assert limiter.allow("user1") is True


def test_fixed_window():
    limiter = RateLimiter(3, 60.0, Algorithm.FIXED_WINDOW)
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is False


def test_token_bucket():
    limiter = RateLimiter(3, 60.0, Algorithm.TOKEN_BUCKET)
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is False


def test_different_keys_independent():
    limiter = RateLimiter(1, 60.0)
    assert limiter.allow("user1") is True
    assert limiter.allow("user2") is True
    assert limiter.allow("user1") is False
    assert limiter.allow("user2") is False


def test_limit_decorator():
    limiter = RateLimiter(10, 60.0)

    @limiter.limit("2/second")
    def my_func():
        return "ok"

    assert my_func() == "ok"
    assert my_func() == "ok"
    with pytest.raises(RateLimitExceeded):
        my_func()


def test_invalid_requests():
    with pytest.raises(ValueError, match="requests must be positive"):
        RateLimiter(0, 60.0)


def test_invalid_negative_requests():
    with pytest.raises(ValueError, match="requests must be positive"):
        RateLimiter(-1, 60.0)


def test_invalid_window_seconds():
    with pytest.raises(ValueError, match="window_seconds must be positive"):
        RateLimiter(10, 0)


def test_invalid_negative_window():
    with pytest.raises(ValueError, match="window_seconds must be positive"):
        RateLimiter(10, -1.0)


def test_active_keys():
    limiter = RateLimiter(5, 60.0)
    limiter.allow("user1")
    limiter.allow("user2")
    keys = limiter.active_keys()
    assert "user1" in keys
    assert "user2" in keys


def test_active_keys_empty():
    limiter = RateLimiter(5, 60.0)
    assert limiter.active_keys() == []


def test_reset_all():
    limiter = RateLimiter(2, 60.0)
    limiter.allow("user1")
    limiter.allow("user2")
    limiter.reset_all()
    assert limiter.active_keys() == []
    assert limiter.allow("user1") is True


def test_reset_nonexistent_key():
    limiter = RateLimiter(5, 60.0)
    limiter.reset("nonexistent")  # should not raise


def test_rate_limit_exceeded_has_status():
    limiter = RateLimiter(1, 60.0)
    limiter.allow("user1")
    status = limiter.status("user1")
    assert status.allowed is False
    exc = RateLimitExceeded(status)
    assert exc.status.remaining == 0
    assert exc.status.limit == 1


def test_three_keys_independent():
    limiter = RateLimiter(1, 60.0)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("c") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is False
    assert limiter.allow("c") is False


def test_decorator_preserves_name():
    limiter = RateLimiter(10, 60.0)

    @limiter.limit("5/second")
    def my_function():
        """My docstring."""
        pass

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


def test_token_bucket_remaining():
    limiter = RateLimiter(3, 60.0, Algorithm.TOKEN_BUCKET)
    status = limiter.status("user1")
    assert status.remaining == 2  # one consumed by status check
    status = limiter.status("user1")
    assert status.remaining == 1


def test_fixed_window_remaining():
    limiter = RateLimiter(3, 60.0, Algorithm.FIXED_WINDOW)
    status = limiter.status("user1")
    assert status.remaining == 2
    status = limiter.status("user1")
    assert status.remaining == 1


def test_rate_parse_day():
    limiter = RateLimiter(10, 60.0)

    @limiter.limit("1/day")
    def daily():
        return "ok"

    assert daily() == "ok"
    with pytest.raises(RateLimitExceeded):
        daily()


def test_rate_parse_hours():
    limiter = RateLimiter(10, 60.0)

    @limiter.limit("100/hours")
    def hourly():
        return "ok"

    assert hourly() == "ok"


# --- Leaky bucket tests (v0.4.0) ---


def test_leaky_bucket_allows():
    limiter = RateLimiter(5, 60.0, Algorithm.LEAKY_BUCKET)
    assert limiter.allow("user1") is True


def test_leaky_bucket_exhausts():
    limiter = RateLimiter(3, 60.0, Algorithm.LEAKY_BUCKET)
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is False


def test_leaky_bucket_remaining():
    limiter = RateLimiter(3, 60.0, Algorithm.LEAKY_BUCKET)
    status = limiter.status("user1")
    assert status.allowed is True
    assert status.remaining == 2
    status = limiter.status("user1")
    assert status.remaining == 1


def test_leaky_bucket_reset():
    limiter = RateLimiter(2, 60.0, Algorithm.LEAKY_BUCKET)
    limiter.allow("user1")
    limiter.allow("user1")
    assert limiter.allow("user1") is False
    limiter.reset("user1")
    assert limiter.allow("user1") is True


def test_leaky_bucket_different_keys():
    limiter = RateLimiter(1, 60.0, Algorithm.LEAKY_BUCKET)
    assert limiter.allow("user1") is True
    assert limiter.allow("user2") is True
    assert limiter.allow("user1") is False
    assert limiter.allow("user2") is False


def test_leaky_bucket_active_keys():
    limiter = RateLimiter(5, 60.0, Algorithm.LEAKY_BUCKET)
    limiter.allow("a")
    limiter.allow("b")
    keys = limiter.active_keys()
    assert "a" in keys
    assert "b" in keys


def test_leaky_bucket_reset_all():
    limiter = RateLimiter(2, 60.0, Algorithm.LEAKY_BUCKET)
    limiter.allow("user1")
    limiter.allow("user2")
    limiter.reset_all()
    assert limiter.active_keys() == []


# --- Rate limiter group tests (v0.4.0) ---


def test_group_shared_limit():
    limiter = RateLimiter(3, 60.0)
    group = RateLimiterGroup(limiter, ["user1", "user2", "user3"])
    assert group.allow("user1") is True
    assert group.allow("user2") is True
    assert group.allow("user3") is True
    assert group.allow("user1") is False


def test_group_keys_property():
    limiter = RateLimiter(5, 60.0)
    group = RateLimiterGroup(limiter, ["a", "b", "c"])
    assert group.keys == ["a", "b", "c"]


def test_group_rejects_unknown_key():
    limiter = RateLimiter(5, 60.0)
    group = RateLimiterGroup(limiter, ["user1"])
    with pytest.raises(ValueError, match="not part of this group"):
        group.allow("unknown")


def test_group_status():
    limiter = RateLimiter(3, 60.0)
    group = RateLimiterGroup(limiter, ["a", "b"])
    group.allow("a")
    status = group.status("b")
    assert isinstance(status, LimitStatus)
    assert status.remaining < 3


def test_group_status_rejects_unknown_key():
    limiter = RateLimiter(5, 60.0)
    group = RateLimiterGroup(limiter, ["user1"])
    with pytest.raises(ValueError, match="not part of this group"):
        group.status("unknown")


def test_group_reset():
    limiter = RateLimiter(2, 60.0)
    group = RateLimiterGroup(limiter, ["a", "b"])
    group.allow("a")
    group.allow("b")
    assert group.allow("a") is False
    group.reset()
    assert group.allow("a") is True


def test_group_get_stats():
    limiter = RateLimiter(5, 60.0)
    group = RateLimiterGroup(limiter, ["a", "b"])
    group.allow("a")
    group.allow("b")
    stats = group.get_stats()
    assert isinstance(stats, RateLimiterStats)
    assert stats.current_usage == 2
    assert stats.remaining == 3
    assert stats.limit == 5


def test_group_independent_from_individual_keys():
    limiter = RateLimiter(3, 60.0)
    group = RateLimiterGroup(limiter, ["user1", "user2"])
    # Group uses a shared internal key, individual keys are separate
    assert limiter.allow("user1") is True
    assert group.allow("user1") is True
    assert group.allow("user2") is True
    assert group.allow("user1") is True
    assert group.allow("user2") is False  # group exhausted


# --- get_stats tests (v0.4.0) ---


def test_get_stats_sliding_window():
    limiter = RateLimiter(5, 60.0)
    stats = limiter.get_stats("user1")
    assert isinstance(stats, RateLimiterStats)
    assert stats.current_usage == 0
    assert stats.remaining == 5
    assert stats.limit == 5


def test_get_stats_after_requests():
    limiter = RateLimiter(5, 60.0)
    limiter.allow("user1")
    limiter.allow("user1")
    stats = limiter.get_stats("user1")
    assert stats.current_usage == 2
    assert stats.remaining == 3


def test_get_stats_does_not_consume():
    limiter = RateLimiter(3, 60.0)
    limiter.allow("user1")
    stats1 = limiter.get_stats("user1")
    stats2 = limiter.get_stats("user1")
    assert stats1.current_usage == stats2.current_usage
    assert stats1.remaining == stats2.remaining


def test_get_stats_fixed_window():
    limiter = RateLimiter(5, 60.0, Algorithm.FIXED_WINDOW)
    limiter.allow("user1")
    stats = limiter.get_stats("user1")
    assert stats.current_usage == 1
    assert stats.remaining == 4
    assert stats.limit == 5


def test_get_stats_token_bucket():
    limiter = RateLimiter(5, 60.0, Algorithm.TOKEN_BUCKET)
    limiter.allow("user1")
    stats = limiter.get_stats("user1")
    assert stats.remaining >= 3  # at least 3 remaining (some refill possible)
    assert stats.limit == 5


def test_get_stats_leaky_bucket():
    limiter = RateLimiter(5, 60.0, Algorithm.LEAKY_BUCKET)
    limiter.allow("user1")
    stats = limiter.get_stats("user1")
    assert stats.limit == 5
    assert stats.remaining >= 4


def test_get_stats_reset_at_present():
    limiter = RateLimiter(5, 60.0)
    limiter.allow("user1")
    stats = limiter.get_stats("user1")
    assert stats.reset_at > 0


# --- Async context manager tests (v0.4.0) ---


def test_async_context_manager():
    async def run():
        limiter = RateLimiter(5, 60.0)
        async with limiter as lim:
            assert lim.allow("user1") is True
        # limiter is still usable after exiting
        assert limiter.allow("user1") is True

    asyncio.run(run())


def test_async_context_manager_with_acquire():
    async def run():
        limiter = RateLimiter(5, 60.0)
        async with limiter:
            status = await limiter.async_acquire("user1")
            assert status.allowed is True

    asyncio.run(run())


# --- Standalone rate_limit decorator tests (v0.4.0) ---


def test_rate_limit_decorator_basic():
    @rate_limit(calls=2, period=60)
    def my_func():
        return "ok"

    assert my_func() == "ok"
    assert my_func() == "ok"
    with pytest.raises(RateLimitExceeded):
        my_func()


def test_rate_limit_decorator_preserves_name():
    @rate_limit(calls=10, period=60)
    def my_function():
        """My docstring."""
        pass

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


def test_rate_limit_decorator_with_algorithm():
    @rate_limit(calls=2, period=60, algorithm=Algorithm.TOKEN_BUCKET)
    def bucket_func():
        return "ok"

    assert bucket_func() == "ok"
    assert bucket_func() == "ok"
    with pytest.raises(RateLimitExceeded):
        bucket_func()


def test_rate_limit_decorator_with_args():
    @rate_limit(calls=3, period=60)
    def add(a, b):
        return a + b

    assert add(1, 2) == 3
    assert add(3, 4) == 7
    assert add(5, 6) == 11
    with pytest.raises(RateLimitExceeded):
        add(7, 8)


def test_rate_limit_decorator_async():
    @rate_limit(calls=2, period=60)
    async def async_func():
        return "async_ok"

    async def run():
        assert await async_func() == "async_ok"
        assert await async_func() == "async_ok"
        with pytest.raises(RateLimitExceeded):
            await async_func()

    asyncio.run(run())


def test_rate_limit_decorator_async_preserves_name():
    @rate_limit(calls=10, period=60)
    async def async_function():
        """Async docstring."""
        pass

    assert async_function.__name__ == "async_function"
    assert async_function.__doc__ == "Async docstring."


def test_rate_limit_decorator_leaky_bucket():
    @rate_limit(calls=2, period=60, algorithm=Algorithm.LEAKY_BUCKET)
    def leaky_func():
        return "ok"

    assert leaky_func() == "ok"
    assert leaky_func() == "ok"
    with pytest.raises(RateLimitExceeded):
        leaky_func()


# --- Algorithm enum tests ---


def test_algorithm_leaky_bucket_value():
    assert Algorithm.LEAKY_BUCKET.value == "leaky_bucket"


def test_all_algorithms_in_enum():
    names = {a.name for a in Algorithm}
    assert "FIXED_WINDOW" in names
    assert "SLIDING_WINDOW" in names
    assert "TOKEN_BUCKET" in names
    assert "LEAKY_BUCKET" in names
