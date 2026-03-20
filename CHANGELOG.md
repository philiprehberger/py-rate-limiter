# Changelog
## 0.2.4- Add pytest and mypy tool configuration to pyproject.toml

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
