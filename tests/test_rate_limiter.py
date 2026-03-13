import pytest
from philiprehberger_rate_limiter import RateLimiter, Algorithm, LimitStatus, RateLimitExceeded


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


# --- New tests for v0.2.0 ---


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
