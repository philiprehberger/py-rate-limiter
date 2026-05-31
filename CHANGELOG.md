# Changelog

## 0.6.0 (2026-05-30)

- Add `RateLimiter.remaining(key)` returning unconsumed budget
- Add `RateLimiter.reset_at(key)` returning the UNIX timestamp when capacity becomes available

## 0.5.0 (2026-04-27)

- Add `format_status(key)` returning a human-readable line ("15/100 requests used (85 remaining); resets in 23.5s") for logging and CLI output

## 0.4.0 (2026-04-01)

- Add `LEAKY_BUCKET` algorithm as a fourth strategy option
- Add `RateLimiterGroup` for shared rate limits across multiple keys
- Add `get_stats(key)` method returning `RateLimiterStats` with current usage, remaining tokens, and reset time without consuming a request
- Add `RateLimiterStats` dataclass for usage statistics
- Add async context manager support (`async with limiter:`)
- Add standalone `rate_limit(calls, period, algorithm)` decorator for functions
- Add async function support in `rate_limit` decorator

## 0.3.1 (2026-03-31)

- Standardize README to 3-badge format with emoji Support section
- Update CI checkout action to v5 for Node.js 24 compatibility

## 0.3.0 (2026-03-27)

- Add `async_acquire(key)` method for async usage with `asyncio.sleep()` polling
- Add `wait(key, timeout=10.0)` method for synchronous blocking wait
- Add pytest and mypy configuration to `pyproject.toml`
- Add issue templates, PR template, and Dependabot config
- Update README with full badge set and Support section

## 0.2.3 (2026-03-22)

- Add Development section to README

## 0.2.0 (2026-03-18)

- Add `active_keys()` method for monitoring tracked keys
- Add `reset_all()` method to clear all rate limit state
- Validate constructor arguments (requests and window_seconds must be positive)
- Expand test suite with 15 new tests (24 total)

## 0.1.1 (2026-03-13)

- Add project URLs to pyproject.toml

## 0.1.0 (2026-03-10)

- Initial release
- Fixed window, sliding window, and token bucket algorithms
- Per-key rate limiting
- Thread-safe with status reporting
- Decorator support
