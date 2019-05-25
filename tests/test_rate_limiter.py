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
