# Changelog

## 0.3.0 (2026-03-27)

- Add `async_acquire(key)` method for async usage with `asyncio.sleep()` polling
- Add `wait(key, timeout=10.0)` method for synchronous blocking wait
- Add pytest and mypy configuration to `pyproject.toml`
- Add issue templates, PR template, and Dependabot config
- Update README with full badge set and Support section

## 0.2.3

- Add Development section to README

## 0.2.0

- Add `active_keys()` method for monitoring tracked keys
- Add `reset_all()` method to clear all rate limit state
- Validate constructor arguments (requests and window_seconds must be positive)
- Expand test suite with 15 new tests (24 total)

## 0.1.1

- Add project URLs to pyproject.toml

## 0.1.0 (2026-03-10)

- Initial release
- Fixed window, sliding window, and token bucket algorithms
- Per-key rate limiting
- Thread-safe with status reporting
- Decorator support
